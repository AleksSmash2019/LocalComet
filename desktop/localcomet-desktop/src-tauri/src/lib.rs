mod app_data_root;
mod artifact_acquisition;
mod artifact_trust;
mod control_plane;
mod ipc;
mod knowledge;
mod managed_runtime;
mod single_instance;
mod startup;
mod supervisor;
mod windows_job;

use artifact_acquisition::{
    cancel_artifact_download, get_artifact_download_state, list_approved_downloadable_artifacts,
    remove_managed_model, start_approved_artifact_download, ArtifactAcquisitionManager,
};
use artifact_trust::{
    managed_artifact_validation_status, managed_installed_artifacts, managed_model_catalog,
    managed_model_readiness, managed_runtime_catalog, ArtifactTrustService,
};
use control_plane::{
    control_plane_bootstrap, control_plane_cancel_turn, control_plane_close_session,
    control_plane_create_session, control_plane_create_thread, control_plane_get_turn_status,
    control_plane_start_mock_turn, knowledge_review_decision_create, knowledge_review_get,
    knowledge_review_list, knowledge_review_refresh, knowledge_review_snapshot, model_binding_set,
    model_gateway_catalog, model_gateway_list_models, model_gateway_probe, model_turn_cancel,
    model_turn_start, ControlPlaneBridge,
};
use knowledge::{knowledge_turn_decide, knowledge_turn_preview};
use managed_runtime::{
    managed_runtime_logs, managed_runtime_start, managed_runtime_status, managed_runtime_stop,
    ManagedRuntimeSupervisor,
};
use std::sync::Arc;
use std::time::Duration;
use supervisor::{DesktopSidecarSupervisor, SupervisorError};
use tauri::Manager;

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
        .setup(|app| {
            startup::record(startup::StartupPhase::BackendStart, "begin", "LC_START_100");
            let local_data_dir = match app.path().local_data_dir() {
                Ok(path) => path,
                Err(_) => {
                    startup::report_failure(startup::StartupPhase::BackendStart, "LC_START_101");
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
                    startup::report_failure(startup::StartupPhase::BackendStart, "LC_START_101");
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
                let (phase, code) = match error {
                    SupervisorError::ReadinessTimeout => {
                        (startup::StartupPhase::BackendReadiness, "LC_START_102")
                    }
                    SupervisorError::ExitedBeforeReady => {
                        (startup::StartupPhase::BackendReadiness, "LC_START_103")
                    }
                    SupervisorError::Unavailable(_) | SupervisorError::Io(_) => {
                        (startup::StartupPhase::BackendStart, "LC_START_101")
                    }
                };
                let _ = supervisor.shutdown();
                startup::report_failure(phase, code);
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
            let Some(window) = app.get_webview_window("main") else {
                let _ = supervisor.shutdown();
                startup::report_failure(startup::StartupPhase::WindowDisplay, "LC_START_201");
                app.handle().exit(1);
                return Ok(());
            };
            if window.show().is_err() {
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
            managed_runtime_catalog,
            managed_model_catalog,
            managed_installed_artifacts,
            managed_artifact_validation_status,
            managed_model_readiness,
            list_approved_downloadable_artifacts,
            start_approved_artifact_download,
            get_artifact_download_state,
            cancel_artifact_download,
            remove_managed_model,
            managed_runtime_start,
            managed_runtime_stop,
            managed_runtime_logs
        ])
        .run(tauri::generate_context!());

    if run_result.is_err() {
        startup::report_failure(startup::StartupPhase::WindowDisplay, "LC_START_202");
    }
}
