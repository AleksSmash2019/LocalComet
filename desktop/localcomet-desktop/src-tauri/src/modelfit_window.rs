use tauri::{command, AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

/// Open the ModelFit helper window as an OWNED window of "main".
///
/// The frontend cannot pass `parent` through the JS
/// `plugin:webview|create_webview_window` command: with the owner option the
/// command never settles (reproduced via CDP on tauri 2.11.5 — the async IPC
/// handler blocks in `WindowBuilder::owner`/`hwnd` resolution). Building the
/// window here applies the owner reliably: the window stays above the main
/// window, minimizes/closes with it, and no longer floats detached in the
/// taskbar/Alt-Tab.
#[command]
pub async fn open_modelfit_window(app: AppHandle) -> Result<(), String> {
    // The label is fixed so repeated sidebar clicks focus the same window
    // instead of failing on a duplicate create.
    if let Some(existing) = app.get_webview_window("modelfit") {
        let _ = existing.show();
        let _ = existing.set_focus();
        return Ok(());
    }
    let main = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;
    // Window ownership must be resolved where the owner HWND is reachable;
    // build synchronously on the caller's thread.
    WebviewWindowBuilder::new(&app, "modelfit", WebviewUrl::App("/modelfit.html".into()))
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
}
