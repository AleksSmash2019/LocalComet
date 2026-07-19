mod control_plane;
mod ipc;
mod knowledge;
mod managed_runtime;
mod supervisor;
mod windows_job;

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
    managed_model_catalog, managed_runtime_logs, managed_runtime_start, managed_runtime_status,
    managed_runtime_stop, ManagedRuntimeSupervisor,
};
use std::sync::Arc;
use supervisor::DesktopSidecarSupervisor;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let supervisor = Arc::new(DesktopSidecarSupervisor::default());
            let bridge = Arc::new(ControlPlaneBridge::new(
                Arc::clone(&supervisor),
                app.handle().clone(),
            ));
            supervisor.set_frame_router(bridge.clone());
            let _ = supervisor.start();
            let _ = supervisor.send_health_probe();
            bridge.emit_sidecar_status();
            let snapshot = supervisor.snapshot();
            let _ = (
                snapshot.running,
                snapshot.saw_python_hello,
                snapshot.saw_goodbye,
                snapshot.last_frame,
                snapshot.stderr_tail,
            );
            app.manage(Arc::clone(&supervisor));
            app.manage(bridge);
            app.manage(Arc::new(ManagedRuntimeSupervisor::production()));
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                let runtime = window.state::<Arc<ManagedRuntimeSupervisor>>();
                let bridge = window.state::<Arc<ControlPlaneBridge>>();
                let _ = runtime.stop(&bridge);
                let supervisor = window.state::<Arc<DesktopSidecarSupervisor>>();
                let _ = supervisor.shutdown();
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
            managed_model_catalog,
            managed_runtime_start,
            managed_runtime_stop,
            managed_runtime_logs
        ])
        .run(tauri::generate_context!())
        .expect("failed to run LocalComet desktop shell");
}
