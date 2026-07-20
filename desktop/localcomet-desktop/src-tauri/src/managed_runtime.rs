use crate::artifact_trust::{ArtifactTrustService, ValidatedRuntimeModel};
use crate::control_plane::{BridgeError, ControlPlaneBridge, ControlPlaneMethod};
use crate::windows_job::{ContainedManagedRuntimeProcess, ManagedRuntimeLaunchSpec};
use serde::Serialize;
use serde_json::{json, Value};
use std::ffi::OsString;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::State;

#[cfg(windows)]
use std::os::windows::fs::MetadataExt;

#[cfg(windows)]
use windows_sys::Win32::Security::Cryptography::{
    BCryptGenRandom, BCRYPT_USE_SYSTEM_PREFERRED_RNG,
};

const ENGINE_ID: &str = "llama.cpp";
const MAX_LOG_BYTES: usize = 256 * 1024;
const MAX_LOG_LINES: usize = 200;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(300);
const REQUIRED_FLAGS: &[&str] = &[
    "--model",
    "--host",
    "--port",
    "--api-key-file",
    "--no-webui",
    "--no-agent",
    "--ctx-size",
    "--n-predict",
];

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub enum ManagedRuntimeState {
    NotInstalled,
    Stopped,
    Validating,
    Starting,
    Ready,
    Stopping,
    Failed,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeStatus {
    pub engine: &'static str,
    pub state: ManagedRuntimeState,
    pub installation: String,
    pub runtime_version: Option<String>,
    pub runtime_instance_id: Option<String>,
    pub runtime_instance_fingerprint: Option<String>,
    pub model_id: Option<String>,
    pub model_display_name: Option<String>,
    pub binding_fingerprint: Option<String>,
    pub last_error: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeStartResponse {
    pub state: ManagedRuntimeState,
    pub provider_id: &'static str,
    pub model_id: String,
    pub model_display_name: String,
    pub runtime_instance_id: String,
    pub runtime_instance_fingerprint: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeStopResponse {
    pub state: ManagedRuntimeState,
    pub stopped: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeLogs {
    pub stdout_tail: Vec<String>,
    pub stderr_tail: Vec<String>,
}

#[derive(Debug)]
pub struct ManagedRuntimeError {
    code: &'static str,
    message: String,
}

impl ManagedRuntimeError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: sanitize_text(&message.into(), 240),
        }
    }
}

impl From<ManagedRuntimeError> for BridgeError {
    fn from(value: ManagedRuntimeError) -> Self {
        BridgeError {
            code: value.code.into(),
            message: value.message,
        }
    }
}

struct ActiveRuntime {
    process: ContainedManagedRuntimeProcess,
    stdout_reader: Option<thread::JoinHandle<()>>,
    stderr_reader: Option<thread::JoinHandle<()>>,
    api_key_file: PathBuf,
    credential: String,
    port: u16,
    runtime_instance_id: String,
    runtime_instance_fingerprint: String,
    binding_fingerprint: String,
    model_id: String,
    model_display_name: String,
    _model_handle: File,
    _runtime_handles: Vec<File>,
}

#[derive(Default, Debug)]
struct LogTail {
    bytes: usize,
    lines: Vec<String>,
}

struct ManagedRuntimeInner {
    state: ManagedRuntimeState,
    runtime_version: Option<String>,
    last_error: Option<String>,
    active: Option<ActiveRuntime>,
    stdout_tail: Arc<Mutex<LogTail>>,
    stderr_tail: Arc<Mutex<LogTail>>,
}

impl Default for ManagedRuntimeInner {
    fn default() -> Self {
        Self {
            state: ManagedRuntimeState::NotInstalled,
            runtime_version: None,
            last_error: None,
            active: None,
            stdout_tail: Arc::new(Mutex::new(LogTail::default())),
            stderr_tail: Arc::new(Mutex::new(LogTail::default())),
        }
    }
}

pub struct ManagedRuntimeSupervisor {
    artifacts: Arc<ArtifactTrustService>,
    lifecycle: Mutex<()>,
    inner: Mutex<ManagedRuntimeInner>,
}

impl ManagedRuntimeSupervisor {
    pub fn new(artifacts: Arc<ArtifactTrustService>) -> Self {
        Self {
            artifacts,
            lifecycle: Mutex::new(()),
            inner: Mutex::new(ManagedRuntimeInner::default()),
        }
    }

    pub fn status(&self) -> ManagedRuntimeStatus {
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        let runtime_installed = self.artifacts.has_valid_runtime();
        if inner.active.is_none() && !runtime_installed {
            inner.state = ManagedRuntimeState::NotInstalled;
        } else if inner.active.is_none() && inner.state == ManagedRuntimeState::NotInstalled {
            inner.state = ManagedRuntimeState::Stopped;
        }
        let active = inner.active.as_ref();
        ManagedRuntimeStatus {
            engine: ENGINE_ID,
            state: inner.state.clone(),
            installation: if runtime_installed {
                "Installed".into()
            } else {
                "Not installed".into()
            },
            runtime_version: inner.runtime_version.clone(),
            runtime_instance_id: active.map(|item| item.runtime_instance_id.clone()),
            runtime_instance_fingerprint: active
                .map(|item| item.runtime_instance_fingerprint.clone()),
            model_id: active.map(|item| item.model_id.clone()),
            model_display_name: active.map(|item| item.model_display_name.clone()),
            binding_fingerprint: active.map(|item| item.binding_fingerprint.clone()),
            last_error: inner.last_error.clone(),
        }
    }

    pub fn logs(&self) -> ManagedRuntimeLogs {
        let inner = self.inner.lock().expect("managed runtime lock poisoned");
        let stdout_tail = inner
            .stdout_tail
            .lock()
            .expect("stdout tail poisoned")
            .lines
            .clone();
        let stderr_tail = inner
            .stderr_tail
            .lock()
            .expect("stderr tail poisoned")
            .lines
            .clone();
        ManagedRuntimeLogs {
            stdout_tail,
            stderr_tail,
        }
    }

    pub fn start(
        &self,
        model_id: &str,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedRuntimeStartResponse, BridgeError> {
        let _lifecycle = self
            .lifecycle
            .lock()
            .expect("managed runtime lifecycle lock poisoned");
        {
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if inner.active.is_some()
                || matches!(
                    inner.state,
                    ManagedRuntimeState::Validating
                        | ManagedRuntimeState::Starting
                        | ManagedRuntimeState::Ready
                        | ManagedRuntimeState::Stopping
                )
            {
                return Err(ManagedRuntimeError::new("busy", "managed runtime is busy").into());
            }
            inner.state = ManagedRuntimeState::Validating;
            inner.last_error = None;
        }

        let start_result = self.start_inner(model_id);
        match start_result {
            Ok(response) => {
                let attach = self.attach_payload_for_active()?;
                if let Err(error) = bridge.request(ControlPlaneMethod::ModelManagedAttach, attach) {
                    let _ = self.stop_inner(bridge);
                    self.set_state(
                        ManagedRuntimeState::Failed,
                        Some("managed provider attach failed"),
                    );
                    return Err(error);
                }
                self.set_state(ManagedRuntimeState::Ready, None);
                Ok(response)
            }
            Err(error) => {
                self.set_state(ManagedRuntimeState::Failed, Some(&error.message));
                Err(error)
            }
        }
    }

    pub fn stop(
        &self,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedRuntimeStopResponse, BridgeError> {
        let _lifecycle = self
            .lifecycle
            .lock()
            .expect("managed runtime lifecycle lock poisoned");
        self.stop_inner(bridge)
    }

    fn stop_inner(
        &self,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedRuntimeStopResponse, BridgeError> {
        self.set_state(ManagedRuntimeState::Stopping, None);
        let _ = bridge.request(ControlPlaneMethod::ModelManagedDetach, json!({}));
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        if let Some(mut active) = inner.active.take() {
            active.process.terminate(0);
            let _ = active.process.wait_bounded(3000);
            if let Some(handle) = active.stdout_reader.take() {
                let _ = handle.join();
            }
            if let Some(handle) = active.stderr_reader.take() {
                let _ = handle.join();
            }
            let _ = fs::remove_file(&active.api_key_file);
            active.credential.clear();
        }
        inner.runtime_version = None;
        inner.state = if self.artifacts.has_valid_runtime() {
            ManagedRuntimeState::Stopped
        } else {
            ManagedRuntimeState::NotInstalled
        };
        Ok(ManagedRuntimeStopResponse {
            state: inner.state.clone(),
            stopped: true,
        })
    }

    fn start_inner(&self, model_id: &str) -> Result<ManagedRuntimeStartResponse, BridgeError> {
        let roots = self.artifacts.roots();
        fs::create_dir_all(&roots.runtime_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "runtime root unavailable"))?;
        fs::create_dir_all(&roots.model_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "model root unavailable"))?;
        fs::create_dir_all(&roots.state_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "runtime state unavailable"))?;
        ensure_local_safe_root(&roots.app_data_root, &roots.runtime_root)?;
        ensure_local_safe_root(&roots.app_data_root, &roots.model_root)?;
        ensure_local_safe_root(&roots.app_data_root, &roots.state_root)?;

        let launch = self.artifacts.resolve_launch(model_id)?;
        verify_runtime_capabilities(&launch)?;
        let credential = generate_credential()?;
        let port = select_ephemeral_loopback_port()?;
        let api_key_file = write_private_api_key_file(&roots.state_root, &credential)?;
        let alias = safe_alias(&launch.model_id);
        let runtime_instance_id = hex_bytes(&random_bytes(16)?);
        let runtime_instance_fingerprint = sha256_text(&format!(
            "{}:{}:{}",
            launch.runtime_id, launch.runtime_release_tag, runtime_instance_id
        ));
        let binding_fingerprint = sha256_text(&format!(
            "managed:{}:{}",
            runtime_instance_id, launch.model_id
        ));

        self.set_state(ManagedRuntimeState::Starting, None);
        let spec = ManagedRuntimeLaunchSpec {
            executable: launch.executable.clone(),
            args: runtime_args(&launch.model_path, port, &api_key_file, &alias),
            current_dir: launch.package_dir.clone(),
            env: sanitized_runtime_environment(),
        };
        let mut process = match ContainedManagedRuntimeProcess::spawn(&spec) {
            Ok(process) => process,
            Err(_) => {
                let _ = fs::remove_file(&api_key_file);
                return Err(ManagedRuntimeError::new(
                    "launch_failed",
                    "managed runtime launch failed",
                )
                .into());
            }
        };
        let inner = self.inner.lock().expect("managed runtime lock poisoned");
        let stdout_tail = Arc::clone(&inner.stdout_tail);
        let stderr_tail = Arc::clone(&inner.stderr_tail);
        drop(inner);
        let mut stdout_reader = process.take_stdout().map(|stdout| {
            spawn_log_reader(
                stdout,
                stdout_tail,
                self.redaction_markers(&credential, &api_key_file),
            )
        });
        let mut stderr_reader = process.take_stderr().map(|stderr| {
            spawn_log_reader(
                stderr,
                stderr_tail,
                self.redaction_markers(&credential, &api_key_file),
            )
        });

        let ready = wait_ready(port, &credential, &alias, STARTUP_TIMEOUT);
        if let Err(error) = ready {
            process.terminate(1);
            let _ = process.wait_bounded(3000);
            if let Some(handle) = stdout_reader.take() {
                let _ = handle.join();
            }
            if let Some(handle) = stderr_reader.take() {
                let _ = handle.join();
            }
            let _ = fs::remove_file(&api_key_file);
            return Err(error.into());
        }

        let response = ManagedRuntimeStartResponse {
            state: ManagedRuntimeState::Ready,
            provider_id: "managed-llama-cpp",
            model_id: launch.model_id.clone(),
            model_display_name: launch.model_display_name.clone(),
            runtime_instance_id: runtime_instance_id.clone(),
            runtime_instance_fingerprint: runtime_instance_fingerprint.clone(),
        };
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        inner.runtime_version = Some(launch.runtime_release_tag);
        inner.active = Some(ActiveRuntime {
            process,
            stdout_reader,
            stderr_reader,
            api_key_file,
            credential,
            port,
            runtime_instance_id,
            runtime_instance_fingerprint,
            binding_fingerprint,
            model_id: launch.model_id,
            model_display_name: launch.model_display_name,
            _model_handle: launch.model_handle,
            _runtime_handles: launch.runtime_handles,
        });
        Ok(response)
    }

    fn attach_payload_for_active(&self) -> Result<Value, BridgeError> {
        let inner = self.inner.lock().expect("managed runtime lock poisoned");
        let active = inner.active.as_ref().ok_or_else(|| {
            ManagedRuntimeError::new("sidecar_unavailable", "managed runtime is not active")
        })?;
        Ok(json!({
            "runtime_instance_id": active.runtime_instance_id,
            "port": active.port,
            "credential": active.credential,
            "expected_model_alias": safe_alias(&active.model_id),
            "model_id": active.model_id,
            "binding_fingerprint": active.binding_fingerprint,
        }))
    }

    fn set_state(&self, state: ManagedRuntimeState, error: Option<&str>) {
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        inner.state = state;
        inner.last_error = error.map(|item| sanitize_text(item, 240));
    }

    fn redaction_markers(&self, credential: &str, api_key_file: &Path) -> Vec<(String, String)> {
        let roots = self.artifacts.roots();
        vec![
            (
                roots.runtime_root.to_string_lossy().into_owned(),
                "<RUNTIME_ROOT>".into(),
            ),
            (
                roots.model_root.to_string_lossy().into_owned(),
                "<MODEL_ROOT>".into(),
            ),
            (
                roots.state_root.to_string_lossy().into_owned(),
                "<RUNTIME_STATE>".into(),
            ),
            (
                api_key_file.to_string_lossy().into_owned(),
                "<API_KEY_FILE>".into(),
            ),
            (credential.into(), "<CREDENTIAL>".into()),
        ]
    }
}

impl Drop for ManagedRuntimeSupervisor {
    fn drop(&mut self) {
        if let Ok(mut inner) = self.inner.lock() {
            if let Some(mut active) = inner.active.take() {
                active.process.terminate(0);
                let _ = active.process.wait_bounded(3000);
                if let Some(handle) = active.stdout_reader.take() {
                    let _ = handle.join();
                }
                if let Some(handle) = active.stderr_reader.take() {
                    let _ = handle.join();
                }
                let _ = fs::remove_file(&active.api_key_file);
                active.credential.clear();
            }
        }
    }
}

fn verify_runtime_capabilities(runtime: &ValidatedRuntimeModel) -> Result<(), ManagedRuntimeError> {
    let version_output = run_capability_probe(runtime, "--version")?;
    if version_output.len() > 4096 {
        return Err(ManagedRuntimeError::new(
            "runtime_incompatible",
            "runtime version output too large",
        ));
    }
    let help_output = run_capability_probe(runtime, "--help")?;
    for flag in REQUIRED_FLAGS {
        if !help_output.contains(flag) {
            return Err(ManagedRuntimeError::new(
                "runtime_incompatible",
                "runtime required flag unsupported",
            ));
        }
    }
    Ok(())
}

fn run_capability_probe(
    runtime: &ValidatedRuntimeModel,
    flag: &str,
) -> Result<String, ManagedRuntimeError> {
    let spec = ManagedRuntimeLaunchSpec {
        executable: runtime.executable.clone(),
        args: vec![OsString::from(flag)],
        current_dir: runtime.package_dir.clone(),
        env: sanitized_runtime_environment(),
    };
    let mut process = ContainedManagedRuntimeProcess::spawn(&spec)
        .map_err(|_| ManagedRuntimeError::new("runtime_incompatible", "runtime probe failed"))?;
    let mut output = String::new();
    if let Some(mut stdout) = process.take_stdout() {
        let _ = stdout.read_to_string(&mut output);
    }
    if !process.wait_bounded(5000) {
        process.terminate(1);
        return Err(ManagedRuntimeError::new(
            "runtime_incompatible",
            "runtime probe timed out",
        ));
    }
    Ok(sanitize_text(&output, 4096))
}

fn runtime_args(model: &Path, port: u16, api_key_file: &Path, alias: &str) -> Vec<OsString> {
    vec![
        OsString::from("--model"),
        model.as_os_str().to_os_string(),
        OsString::from("--host"),
        OsString::from("127.0.0.1"),
        OsString::from("--port"),
        OsString::from(port.to_string()),
        OsString::from("--api-key-file"),
        api_key_file.as_os_str().to_os_string(),
        OsString::from("--no-webui"),
        OsString::from("--no-agent"),
        OsString::from("--ctx-size"),
        OsString::from("4096"),
        OsString::from("--n-predict"),
        OsString::from("512"),
        OsString::from("--alias"),
        OsString::from(alias),
    ]
}

fn sanitized_runtime_environment() -> Vec<(OsString, OsString)> {
    let mut env = Vec::new();
    for key in ["SystemRoot", "WINDIR", "TEMP", "TMP"] {
        if let Some(value) = std::env::var_os(key) {
            env.push((OsString::from(key), value));
        }
    }
    if let Some(system_root) = std::env::var_os("SystemRoot") {
        env.push((
            OsString::from("PATH"),
            PathBuf::from(system_root).join("System32").into_os_string(),
        ));
    }
    env
}

fn wait_ready(
    port: u16,
    credential: &str,
    expected_alias: &str,
    timeout: Duration,
) -> Result<(), ManagedRuntimeError> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        match http_get_json(port, "/health", credential) {
            Ok(value) if value.contains("\"status\"") || value.contains("\"ok\"") => {
                let models = http_get_json(port, "/v1/models", credential)?;
                if models.contains(expected_alias) {
                    return Ok(());
                }
                return Err(ManagedRuntimeError::new(
                    "wrong_model",
                    "managed model alias mismatch",
                ));
            }
            _ => thread::sleep(Duration::from_millis(250)),
        }
    }
    Err(ManagedRuntimeError::new(
        "timeout",
        "managed runtime startup timed out",
    ))
}

fn http_get_json(port: u16, path: &str, credential: &str) -> Result<String, ManagedRuntimeError> {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).map_err(|_| {
        ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint unavailable")
    })?;
    stream
        .set_read_timeout(Some(Duration::from_secs(2)))
        .map_err(|_| ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint timeout"))?;
    let request = format!(
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {credential}\r\nConnection: close\r\nAccept: application/json\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).map_err(|_| {
        ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint write failed")
    })?;
    let mut body = Vec::new();
    stream.take(65_536).read_to_end(&mut body).map_err(|_| {
        ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint read failed")
    })?;
    let text = String::from_utf8_lossy(&body);
    if text.contains(" 30") {
        return Err(ManagedRuntimeError::new(
            "invalid_payload",
            "redirect rejected",
        ));
    }
    if !text.starts_with("HTTP/1.0 200") && !text.starts_with("HTTP/1.1 200") {
        return Err(ManagedRuntimeError::new(
            "sidecar_unavailable",
            "managed endpoint non-200",
        ));
    }
    Ok(text.split("\r\n\r\n").nth(1).unwrap_or("").to_string())
}

fn select_ephemeral_loopback_port() -> Result<u16, ManagedRuntimeError> {
    for _ in 0..3 {
        let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|_| {
            ManagedRuntimeError::new("port_unavailable", "loopback port unavailable")
        })?;
        let port = listener
            .local_addr()
            .map_err(|_| ManagedRuntimeError::new("port_unavailable", "loopback port unavailable"))?
            .port();
        drop(listener);
        if port >= 1024 {
            return Ok(port);
        }
    }
    Err(ManagedRuntimeError::new(
        "port_unavailable",
        "ephemeral port selection failed",
    ))
}

fn write_private_api_key_file(
    state_root: &Path,
    credential: &str,
) -> Result<PathBuf, ManagedRuntimeError> {
    fs::create_dir_all(state_root)
        .map_err(|_| ManagedRuntimeError::new("io_error", "runtime state unavailable"))?;
    let file_name = format!("key-{}.txt", hex_bytes(&random_bytes(16)?));
    let path = state_root.join(file_name);
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
        .map_err(|_| ManagedRuntimeError::new("io_error", "credential file creation failed"))?;
    file.write_all(credential.as_bytes())
        .and_then(|_| file.write_all(b"\n"))
        .map_err(|_| ManagedRuntimeError::new("io_error", "credential file write failed"))?;
    Ok(path)
}

fn generate_credential() -> Result<String, ManagedRuntimeError> {
    Ok(hex_bytes(&random_bytes(32)?))
}

#[cfg(windows)]
fn random_bytes(len: usize) -> Result<Vec<u8>, ManagedRuntimeError> {
    let mut bytes = vec![0_u8; len];
    let status = unsafe {
        BCryptGenRandom(
            std::ptr::null_mut(),
            bytes.as_mut_ptr(),
            bytes.len() as u32,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    };
    if status < 0 {
        return Err(ManagedRuntimeError::new(
            "internal_error",
            "Windows CSPRNG failed",
        ));
    }
    Ok(bytes)
}

#[cfg(not(windows))]
fn random_bytes(len: usize) -> Result<Vec<u8>, ManagedRuntimeError> {
    let now = Instant::now();
    let seed = format!("{now:?}:{len}");
    let mut out = Vec::with_capacity(len);
    while out.len() < len {
        out.extend_from_slice(sha256_text(&format!("{seed}:{}", out.len())).as_bytes());
    }
    out.truncate(len);
    Ok(out)
}

fn ensure_local_safe_root(anchor: &Path, path: &Path) -> Result<(), ManagedRuntimeError> {
    if path.to_string_lossy().starts_with(r"\\") {
        return Err(ManagedRuntimeError::new(
            "invalid_path",
            "UNC path rejected",
        ));
    }
    let relative = path
        .strip_prefix(anchor)
        .map_err(|_| ManagedRuntimeError::new("invalid_path", "managed root escaped app data"))?;
    reject_reparse_point(anchor)?;
    let mut current = anchor.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        reject_reparse_point(&current)?;
    }
    Ok(())
}

fn reject_reparse_point(path: &Path) -> Result<(), ManagedRuntimeError> {
    let meta = fs::symlink_metadata(path)
        .map_err(|_| ManagedRuntimeError::new("invalid_path", "path metadata unavailable"))?;
    if meta.file_type().is_symlink() {
        return Err(ManagedRuntimeError::new("invalid_path", "symlink rejected"));
    }
    #[cfg(windows)]
    {
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0000_0400;
        if meta.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return Err(ManagedRuntimeError::new(
                "invalid_path",
                "reparse point rejected",
            ));
        }
    }
    Ok(())
}

fn sha256_text(text: &str) -> String {
    sha256_bytes(text.as_bytes())
}

fn sha256_bytes(bytes: &[u8]) -> String {
    const H0: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
    ];
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
        0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
        0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
        0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
        0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
        0xc67178f2,
    ];
    let mut data = bytes.to_vec();
    let bit_len = (data.len() as u64) * 8;
    data.push(0x80);
    while data.len() % 64 != 56 {
        data.push(0);
    }
    data.extend_from_slice(&bit_len.to_be_bytes());
    let mut h = H0;
    for chunk in data.chunks(64) {
        let mut w = [0_u32; 64];
        for (index, word) in w.iter_mut().take(16).enumerate() {
            let base = index * 4;
            *word = u32::from_be_bytes([
                chunk[base],
                chunk[base + 1],
                chunk[base + 2],
                chunk[base + 3],
            ]);
        }
        for index in 16..64 {
            let s0 = w[index - 15].rotate_right(7)
                ^ w[index - 15].rotate_right(18)
                ^ (w[index - 15] >> 3);
            let s1 = w[index - 2].rotate_right(17)
                ^ w[index - 2].rotate_right(19)
                ^ (w[index - 2] >> 10);
            w[index] = w[index - 16]
                .wrapping_add(s0)
                .wrapping_add(w[index - 7])
                .wrapping_add(s1);
        }
        let mut a = h[0];
        let mut b = h[1];
        let mut c = h[2];
        let mut d = h[3];
        let mut e = h[4];
        let mut f = h[5];
        let mut g = h[6];
        let mut hh = h[7];
        for index in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[index])
                .wrapping_add(w[index]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }
        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }
    h.iter().map(|word| format!("{word:08x}")).collect()
}

fn hex_bytes(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn sanitize_model_name(name: &str) -> String {
    let cleaned: String = name
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '-' | '_'))
        .take(96)
        .collect();
    if cleaned.is_empty() {
        "model.gguf".into()
    } else {
        cleaned
    }
}

fn safe_alias(model_id: &str) -> String {
    format!(
        "localcomet-{}",
        sanitize_model_name(model_id).replace('.', "-")
    )
}

fn sanitize_text(value: &str, limit: usize) -> String {
    let mut text = value.replace('\0', "");
    for marker in ["sk-", "Bearer ", "bearer ", "Traceback", "C:\\Users\\"] {
        if let Some(index) = text.find(marker) {
            text.replace_range(index.., "<REDACTED>");
        }
    }
    if text.len() > limit {
        text.truncate(limit);
    }
    text
}

fn spawn_log_reader(
    mut file: File,
    tail: Arc<Mutex<LogTail>>,
    markers: Vec<(String, String)>,
) -> thread::JoinHandle<()> {
    thread::Builder::new()
        .name("localcomet-managed-runtime-log".into())
        .spawn(move || {
            let mut buffer = [0_u8; 1024];
            while let Ok(count) = file.read(&mut buffer) {
                if count == 0 {
                    break;
                }
                let mut text = String::from_utf8_lossy(&buffer[..count]).into_owned();
                for (needle, replacement) in &markers {
                    if !needle.is_empty() {
                        text = text.replace(needle, replacement);
                    }
                }
                let mut guard = tail.lock().expect("managed log tail poisoned");
                for line in text.lines() {
                    guard.bytes = guard.bytes.saturating_add(line.len());
                    guard.lines.push(sanitize_text(line, 512));
                    while guard.lines.len() > MAX_LOG_LINES || guard.bytes > MAX_LOG_BYTES {
                        if let Some(first) = guard.lines.first() {
                            guard.bytes = guard.bytes.saturating_sub(first.len());
                        }
                        if !guard.lines.is_empty() {
                            guard.lines.remove(0);
                        } else {
                            break;
                        }
                    }
                }
            }
        })
        .expect("managed runtime log reader spawn failed")
}

#[tauri::command]
pub fn managed_runtime_status(
    state: State<'_, Arc<ManagedRuntimeSupervisor>>,
) -> ManagedRuntimeStatus {
    state.status()
}

#[tauri::command]
pub fn managed_runtime_start(
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
    model_id: String,
) -> Result<ManagedRuntimeStartResponse, BridgeError> {
    if model_id.is_empty() || model_id.len() > 96 || model_id.chars().any(char::is_whitespace) {
        return Err(ManagedRuntimeError::new("invalid_payload", "invalid model id").into());
    }
    runtime.start(&model_id, &bridge)
}

#[tauri::command]
pub fn managed_runtime_stop(
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<ManagedRuntimeStopResponse, BridgeError> {
    runtime.stop(&bridge)
}

#[tauri::command]
pub fn managed_runtime_logs(state: State<'_, Arc<ManagedRuntimeSupervisor>>) -> ManagedRuntimeLogs {
    state.logs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_runtime_args_disable_webui_and_agent() {
        let args = runtime_args(
            Path::new(r"C:\m\model.gguf"),
            12345,
            Path::new(r"C:\k\key.txt"),
            "alias",
        );
        let joined = args
            .iter()
            .map(|item| item.to_string_lossy())
            .collect::<Vec<_>>()
            .join(" ");
        assert!(joined.contains("--host 127.0.0.1"));
        assert!(joined.contains("--no-webui"));
        assert!(joined.contains("--no-agent"));
        assert!(!joined.contains("http://"));
    }

    #[test]
    fn sanitized_environment_removes_proxy_llama_and_hf_names() {
        let env = sanitized_runtime_environment();
        let keys: Vec<String> = env
            .iter()
            .map(|(key, _)| key.to_string_lossy().to_ascii_uppercase())
            .collect();
        assert!(!keys.iter().any(|key| {
            key.starts_with("LLAMA_")
                || key.starts_with("HF_")
                || key.starts_with("HUGGINGFACE_")
                || key.ends_with("PROXY")
        }));
    }
}
