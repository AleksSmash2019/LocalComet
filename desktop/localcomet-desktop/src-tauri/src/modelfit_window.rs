use tauri::{command, AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

/// Open the ModelFit helper window as an OWNED window of "main".
///
/// The frontend cannot pass `parent` through the JS
/// `plugin:webview|create_webview_window` command, and building from a
/// worker thread hangs the same way: on Windows `.parent(&main)` resolves
/// the owner HWND through a blocking roundtrip to the event loop, and from
/// a non-main thread that roundtrip never completes (CDP-verified on tauri
/// 2.11.5 — both paths deadlock and no window is created). The window must
/// therefore be built ON the main thread, where the HWND resolves
/// synchronously. The result travels back over a channel so the command
/// still settles with an honest error.
#[command]
pub async fn open_modelfit_window(app: AppHandle) -> Result<(), String> {
    // The label is fixed so repeated sidebar clicks focus the same window
    // instead of failing on a duplicate create.
    if let Some(existing) = app.get_webview_window("modelfit") {
        let _ = existing.show();
        let _ = existing.set_focus();
        return Ok(());
    }
    let app_for_main = app.clone();
    let (tx, rx) = std::sync::mpsc::channel::<Result<(), String>>();
    app.run_on_main_thread(move || {
        let result = (|| -> Result<(), String> {
            let main = app_for_main
                .get_webview_window("main")
                .ok_or_else(|| "main window not found".to_string())?;
            WebviewWindowBuilder::new(
                &app_for_main,
                "modelfit",
                WebviewUrl::App("/modelfit.html".into()),
            )
            .title("ModelFit AI")
            .inner_size(1100.0, 800.0)
            .min_inner_size(800.0, 600.0)
            .center()
            .resizable(true)
            .maximizable(true)
            .parent(&main)
            .map_err(|e| format!("modelfit owner setup failed: {e}"))?
            .build()
            .map_err(|e| format!("modelfit window build failed: {e}"))?;
            Ok(())
        })();
        let _ = tx.send(result);
    })
    .map_err(|e| format!("modelfit main-thread dispatch failed: {e}"))?;
    // Bounded wait: a dead event loop must not wedge the command forever.
    rx.recv_timeout(std::time::Duration::from_secs(15))
        .map_err(|_| "modelfit window creation timed out".to_string())?
}
