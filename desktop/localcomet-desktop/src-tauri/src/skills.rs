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
    let python = std::env::var_os("LOCALCOMET_TEST_PYTHON")
        .unwrap_or_else(|| std::ffi::OsString::from("python"));

    // SEC-2: resolve the CLI script from a trusted anchor (resource/exe dir,
    // then CARGO_MANIFEST_DIR for dev builds). A bare cwd-relative fallback in
    // an installed app could pick up a planted file from the launch directory.
    let cli_path = std::env::var_os("LOCALCOMET_SKILLS_CLI_PATH")
        .map(PathBuf::from)
        .filter(|p| p.is_file())
        .or_else(|| {
            std::env::current_exe().ok().and_then(|exe| {
                let candidate = exe
                    .parent()?
                    .join("../../../scripts/skills_cli.py")
                    .canonicalize()
                    .ok();
                candidate.filter(|p| p.is_file())
            })
        })
        .or_else(|| {
            option_env!("CARGO_MANIFEST_DIR").map(|manifest| {
                PathBuf::from(manifest)
                    .join("../../scripts/skills_cli.py")
                    .canonicalize()
                    .expect("skills_cli.py must exist next to the crate in dev builds")
            })
        })
        .ok_or_else(|| "skills_cli.py not found in trusted locations".to_string())?;

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

    // SEC-2: minimal environment (mirror of the sidecar sanitiser) — the
    // inherited user environment could smuggle PYTHONPATH/PYTHONSTARTUP
    // execution or proxy redirection into the skill CLI.
    cmd.env_clear();
    cmd.env(
        "SYSTEMROOT",
        std::env::var("SYSTEMROOT").unwrap_or_default(),
    );
    cmd.env("PATH", r"C:\Windows\System32;C:\Windows");
    if let Ok(test_root) = std::env::var("LOCALCOMET_TEST_PROJECT_ROOT") {
        cmd.env("LOCALCOMET_TEST_PROJECT_ROOT", test_root);
    }
    if let Ok(test_py) = std::env::var("LOCALCOMET_TEST_PYTHON") {
        cmd.env("LOCALCOMET_TEST_PYTHON", test_py);
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
pub async fn skills_compile(
    app: AppHandle,
    state: tauri::State<'_, ApprovalState>,
    skill_id: String,
    arguments: serde_json::Value,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<SkillResponse, String> {
    if !arguments.is_object() {
        return Err("workflow arguments must be a JSON object".to_string());
    }
    let semantic_payload = serde_json::json!({
        "action": "compile",
        "skill_id": skill_id,
        "arguments": arguments,
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
    let skill_id = semantic_payload["skill_id"]
        .as_str()
        .ok_or_else(|| "invalid skill id payload".to_string())?
        .to_owned();
    let arguments_json = serde_json::to_string(&semantic_payload["arguments"])
        .map_err(|err| format!("invalid workflow arguments: {err}"))?;
    run_skills_cli(
        &app,
        "compile",
        &["--skill-id", &skill_id, "--arguments", &arguments_json],
    )
    .await
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
