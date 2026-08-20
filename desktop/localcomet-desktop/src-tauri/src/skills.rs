use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;
use tauri::{command, AppHandle, Manager};

use crate::app_data_root::resolve_application_data_root;
use crate::approval_commands::{validate_approval_token, ApprovalState};

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
    // A packaged application must not execute a CLI selected by host test-env
    // variables or the current working directory. Debug builds retain these
    // controlled fallbacks for the developer launcher and integration tests.
    let python = if cfg!(debug_assertions) {
        std::env::var_os("LOCALCOMET_TEST_PYTHON")
            .unwrap_or_else(|| std::ffi::OsString::from("python"))
    } else {
        std::ffi::OsString::from("python")
    };

    let local_data_dir = app.path().local_data_dir().map_err(|e| e.to_string())?;
    let app_root =
        resolve_application_data_root(&local_data_dir).map_err(|e| format!("{:?}", e))?;
    let mut candidates = Vec::new();
    candidates.push(app_root.join("scripts/skills_cli.py"));
    candidates.push(app_root.join("app/scripts/skills_cli.py"));
    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join("scripts/skills_cli.py"));
        candidates.push(resource_dir.join("app/scripts/skills_cli.py"));
    }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(dir) = executable.parent() {
            candidates.push(dir.join("app/scripts/skills_cli.py"));
            candidates.push(dir.join("scripts/skills_cli.py"));
            if let Some(parent) = dir.parent() {
                candidates.push(parent.join("app/scripts/skills_cli.py"));
                candidates.push(parent.join("scripts/skills_cli.py"));
                if let Some(grandparent) = parent.parent() {
                    candidates.push(grandparent.join("app/scripts/skills_cli.py"));
                }
            }
        }
    }
    if cfg!(debug_assertions) {
        for variable in ["LOCALCOMET_SOURCE_ROOT", "LOCALCOMET_TEST_PROJECT_ROOT"] {
            if let Some(root) = std::env::var_os(variable) {
                candidates.push(PathBuf::from(root).join("scripts/skills_cli.py"));
            }
        }
        let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        candidates.extend([
            cwd.join("../../../scripts/skills_cli.py"),
            cwd.join("../../scripts/skills_cli.py"),
            cwd.join("scripts/skills_cli.py"),
        ]);
    }
    let cli_path = candidates
        .iter()
        .find(|candidate| candidate.is_file())
        .cloned()
        .ok_or_else(|| "skills_cli_not_found in approved package locations".to_string())?;
    let skills_root = app_root.join("skills");

    let mut cmd = Command::new(python);
    // The CLI emits ensure_ascii=False JSON. Windows Python may otherwise
    // encode stdout using the active ANSI code page; Rust decodes stdout as
    // UTF-8 before forwarding it to Svelte, which would turn Russian metadata
    // into replacement glyphs. Pin both standard Python encoding switches.
    cmd.env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .arg(&cli_path)
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
        let stderr = String::from_utf8_lossy(&output.stderr);
        let detail = if stdout.trim().is_empty() {
            stderr.trim()
        } else {
            stdout.trim()
        };
        Err(format!("Invalid JSON from CLI: {}", detail))
    }
}

#[command]
pub async fn skills_list(app: AppHandle) -> Result<SkillResponse, String> {
    run_skills_cli(&app, "list", &[]).await
}

#[command]
pub async fn skills_install(
    app: AppHandle,
    state: tauri::State<'_, ApprovalState>,
    archive: String,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<SkillResponse, String> {
    let semantic_payload = serde_json::json!({
        "action": "install",
        "archive": archive,
    });
    validate_approval_token(
        &state,
        "skills.invoke",
        &semantic_payload,
        &token,
        &approval_id,
        &call_id,
    )
    .map_err(|err| format!("{}: {}", err.code, err.message))?;

    let archive = semantic_payload["archive"]
        .as_str()
        .ok_or_else(|| "invalid archive payload".to_string())?
        .to_owned();
    run_skills_cli(&app, "install", &["--archive", &archive]).await
}

#[command]
pub async fn skills_enable(
    app: AppHandle,
    state: tauri::State<'_, ApprovalState>,
    skill_id: String,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<SkillResponse, String> {
    let semantic_payload = serde_json::json!({"action": "enable", "skill_id": skill_id});
    validate_approval_token(
        &state,
        "skills.invoke",
        &semantic_payload,
        &token,
        &approval_id,
        &call_id,
    )
    .map_err(|err| format!("{}: {}", err.code, err.message))?;
    let skill_id = semantic_payload["skill_id"]
        .as_str()
        .ok_or_else(|| "invalid skill id payload".to_string())?
        .to_owned();
    run_skills_cli(&app, "enable", &["--skill-id", &skill_id]).await
}

#[command]
pub async fn skills_disable(
    app: AppHandle,
    state: tauri::State<'_, ApprovalState>,
    skill_id: String,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<SkillResponse, String> {
    let semantic_payload = serde_json::json!({"action": "disable", "skill_id": skill_id});
    validate_approval_token(
        &state,
        "skills.invoke",
        &semantic_payload,
        &token,
        &approval_id,
        &call_id,
    )
    .map_err(|err| format!("{}: {}", err.code, err.message))?;
    let skill_id = semantic_payload["skill_id"]
        .as_str()
        .ok_or_else(|| "invalid skill id payload".to_string())?
        .to_owned();
    run_skills_cli(&app, "disable", &["--skill-id", &skill_id]).await
}

#[command]
pub async fn skills_uninstall(
    app: AppHandle,
    state: tauri::State<'_, ApprovalState>,
    skill_id: String,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<SkillResponse, String> {
    let semantic_payload = serde_json::json!({"action": "uninstall", "skill_id": skill_id});
    validate_approval_token(
        &state,
        "skills.invoke",
        &semantic_payload,
        &token,
        &approval_id,
        &call_id,
    )
    .map_err(|err| format!("{}: {}", err.code, err.message))?;
    let skill_id = semantic_payload["skill_id"]
        .as_str()
        .ok_or_else(|| "invalid skill id payload".to_string())?
        .to_owned();
    run_skills_cli(&app, "uninstall", &["--skill-id", &skill_id]).await
}
