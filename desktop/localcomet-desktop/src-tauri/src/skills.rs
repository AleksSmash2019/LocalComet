use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;
use tauri::{command, AppHandle, Manager};

use crate::app_data_root::resolve_application_data_root;

#[derive(Serialize, Deserialize, Debug)]
pub struct SkillResponse {
    pub success: bool,
    pub result: Option<serde_json::Value>,
    pub error: Option<serde_json::Value>,
}

async fn run_skills_cli(
    app: &AppHandle,
    action: &str,
    args: &[&str],
) -> Result<SkillResponse, String> {
    let python = std::env::var_os("LOCALCOMET_TEST_PYTHON")
        .unwrap_or_else(|| std::ffi::OsString::from("python"));

    // Find the skills_cli.py script
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut cli_path = cwd.join("../../../scripts/skills_cli.py");
    if !cli_path.exists() {
        // Fallback for release build or tests where cwd might be different
        cli_path = cwd.join("../../scripts/skills_cli.py");
    }
    if !cli_path.exists() {
        // Fallback for release build if needed
        cli_path = cwd.join("scripts/skills_cli.py");
    }

    let local_data_dir = app.path().local_data_dir().map_err(|e| e.to_string())?;
    let app_root =
        resolve_application_data_root(&local_data_dir).map_err(|e| format!("{:?}", e))?;
    let skills_root = app_root.join("skills");

    let mut cmd = Command::new(python);
    cmd.arg(&cli_path)
        .arg("--root")
        .arg(skills_root.as_os_str())
        .arg(action);

    for arg in args {
        cmd.arg(arg);
    }

    let output = tauri::async_runtime::spawn_blocking(move || cmd.output())
        .await
        .map_err(|e| format!("Join error: {}", e))?
        .map_err(|e| format!("Failed to execute Python CLI: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    if let Ok(parsed) = serde_json::from_str::<SkillResponse>(&stdout) {
        Ok(parsed)
    } else {
        Err(format!("Invalid JSON from CLI: {}", stdout))
    }
}

#[command]
pub async fn skills_list(app: AppHandle) -> Result<SkillResponse, String> {
    run_skills_cli(&app, "list", &[]).await
}

#[command]
pub async fn skills_install(app: AppHandle, archive: String) -> Result<SkillResponse, String> {
    run_skills_cli(&app, "install", &["--archive", &archive]).await
}

#[command]
pub async fn skills_enable(app: AppHandle, skill_id: String) -> Result<SkillResponse, String> {
    run_skills_cli(&app, "enable", &["--skill-id", &skill_id]).await
}

#[command]
pub async fn skills_disable(app: AppHandle, skill_id: String) -> Result<SkillResponse, String> {
    run_skills_cli(&app, "disable", &["--skill-id", &skill_id]).await
}

#[command]
pub async fn skills_uninstall(app: AppHandle, skill_id: String) -> Result<SkillResponse, String> {
    run_skills_cli(&app, "uninstall", &["--skill-id", &skill_id]).await
}
