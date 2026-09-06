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

/// SEC-2 tail: hard ceiling for one skills-CLI invocation.
const SKILLS_CLI_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(15);

/// SEC-2 tail: pinned interpreter resolution. The bundled production layout
/// keeps python314.dll next to the main exe; dev builds resolve through
/// CARGO_MANIFEST_DIR's target dir. An explicit override exists for tests.
/// The override is debug-only (same policy as supervisor.rs): in a release
/// build a same-user env var must not choose the executed interpreter.
#[cfg(debug_assertions)]
fn test_python_override() -> Option<PathBuf> {
    std::env::var_os("LOCALCOMET_TEST_PYTHON")
        .map(PathBuf::from)
        .filter(|p| p.is_file())
}

#[cfg(not(debug_assertions))]
fn test_python_override() -> Option<PathBuf> {
    None
}

fn resolve_pinned_python() -> Result<PathBuf, String> {
    if let Some(path) = test_python_override() {
        return Ok(path);
    }
    if let Some(exe) = std::env::current_exe().ok().and_then(|exe| {
        let candidate = exe.parent()?.join("python314.dll");
        candidate.is_file().then_some(exe.parent()?.to_path_buf())
    }) {
        return Ok(exe.join("python.exe")).and_then(|p| {
            if p.is_file() {
                Ok(p)
            } else {
                Err("bundled python.exe not found next to python314.dll".to_string())
            }
        });
    }
    if let Some(manifest) = option_env!("CARGO_MANIFEST_DIR") {
        for candidate in [
            PathBuf::from(manifest).join("../../../target/debug/python.exe"),
            PathBuf::from(manifest).join("../../../target/release/python.exe"),
        ] {
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
    }
    Err(
        "pinned python interpreter not found (no override, bundled runtime, or dev target)"
            .to_string(),
    )
}

/// Run a child to completion with a hard deadline; kill the process tree
/// attempt (terminate handle) when the deadline passes.
fn wait_with_timeout(
    mut cmd: Command,
    timeout: std::time::Duration,
) -> Result<std::process::Output, String> {
    use std::io::Read;
    let mut child = cmd
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to execute Python CLI: {e}"))?;
    let deadline = std::time::Instant::now() + timeout;
    loop {
        match child.try_wait().map_err(|e| e.to_string())? {
            Some(status) => {
                let mut stdout = Vec::new();
                let mut stderr = Vec::new();
                if let Some(mut stream) = child.stdout.take() {
                    let _ = stream.read_to_end(&mut stdout);
                }
                if let Some(mut stream) = child.stderr.take() {
                    let _ = stream.read_to_end(&mut stderr);
                }
                return Ok(std::process::Output {
                    status,
                    stdout,
                    stderr,
                });
            }
            None => {
                if std::time::Instant::now() >= deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err("skills CLI timed out".to_string());
                }
                std::thread::sleep(std::time::Duration::from_millis(25));
            }
        }
    }
}

async fn run_skills_cli(
    app: &AppHandle,
    action: &str,
    args: &[&str],
) -> Result<SkillResponse, String> {
    // SEC-2 tail: resolve an absolute, pinned interpreter. A bare "python"
    // from the inherited PATH late-binds to whatever executable a same-user
    // attacker (or a broken install) put first on the path. Resolution order:
    // explicit override → python314.dll sibling of the running exe (bundled
    // runtime layout) → CARGO_MANIFEST_DIR target dir (dev builds). Bare
    // "python" is deliberately not a fallback.
    let python = resolve_pinned_python()?;

    // SEC-2: resolve the CLI script from a trusted anchor (resource/exe dir,
    // then CARGO_MANIFEST_DIR for dev builds). A bare cwd-relative fallback in
    // an installed app could pick up a planted file from the launch directory.
    // The env override is debug-only (same policy as supervisor.rs).
    #[cfg(debug_assertions)]
    let cli_env_override = std::env::var_os("LOCALCOMET_SKILLS_CLI_PATH")
        .map(PathBuf::from)
        .filter(|p| p.is_file());
    #[cfg(not(debug_assertions))]
    let cli_env_override: Option<PathBuf> = None;
    let cli_path = cli_env_override
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
            option_env!("CARGO_MANIFEST_DIR").and_then(|manifest| {
                // CARGO_MANIFEST_DIR = <repo>/desktop/localcomet-desktop/src-tauri;
                // repo scripts live three levels up.
                PathBuf::from(manifest)
                    .join("../../../scripts/skills_cli.py")
                    .canonicalize()
                    .ok()
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

    // SEC-2 tail: the child must not inherit the host's working directory
    // (a launch dir with a planted sitecustomize.py or relative payloads).
    // Anchor it to the app-data root the CLI is already confined to.
    cmd.current_dir(&app_root);

    // SEC-2: minimal environment (mirror of the sidecar sanitiser) — the
    // inherited user environment could smuggle PYTHONPATH/PYTHONSTARTUP
    // execution or proxy redirection into the skill CLI.
    cmd.env_clear();
    cmd.env(
        "SYSTEMROOT",
        std::env::var("SYSTEMROOT").unwrap_or_default(),
    );
    cmd.env("PATH", r"C:\Windows\System32;C:\Windows");
    // Env passthrough is debug-only (same policy as supervisor.rs): a release
    // build must not forward test-root/test-python selections into the child.
    #[cfg(debug_assertions)]
    {
        if let Ok(test_root) = std::env::var("LOCALCOMET_TEST_PROJECT_ROOT") {
            cmd.env("LOCALCOMET_TEST_PROJECT_ROOT", test_root);
        }
        if let Ok(test_py) = std::env::var("LOCALCOMET_TEST_PYTHON") {
            cmd.env("LOCALCOMET_TEST_PYTHON", test_py);
        }
    }

    let output = tauri::async_runtime::spawn_blocking(move || {
        // SEC-2 tail: bounded runtime. The CLI is a local config tool; a hung
        // interpreter must not hold the Tauri command forever. 15s is far
        // above the CLI's normal runtime (list/compile are in-memory ops).
        wait_with_timeout(cmd, SKILLS_CLI_TIMEOUT)
    })
    .await
    .map_err(|e| format!("Join error: {}", e))?
    .map_err(|e| format!("Failed to execute Python CLI: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    if let Ok(parsed) = serde_json::from_str::<SkillResponse>(&stdout) {
        Ok(parsed)
    } else {
        // The CLI stdout is untrusted process output: never echo more than a
        // bounded prefix back to the UI error path.
        let mut prefix = stdout.as_ref();
        if prefix.len() > 256 {
            prefix = &prefix[..256];
        }
        Err(format!("Invalid JSON from CLI: {}", prefix.trim_end()))
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
    // Windows command-line limit is 32767 chars; reject oversized argument
    // JSON before the spawn instead of failing with an unreadable OS error.
    if arguments_json.len() > 16_384 {
        return Err("workflow arguments exceed 16384 bytes".to_string());
    }
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
