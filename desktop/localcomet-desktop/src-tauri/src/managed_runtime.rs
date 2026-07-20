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
use std::os::windows::fs::OpenOptionsExt;

#[cfg(windows)]
use windows_sys::Win32::Foundation::{ERROR_INSUFFICIENT_BUFFER, NO_ERROR};

#[cfg(windows)]
use windows_sys::Win32::NetworkManagement::IpHelper::{
    GetExtendedTcpTable, MIB_TCPROW_OWNER_PID, TCP_TABLE_OWNER_PID_LISTENER,
};

#[cfg(windows)]
use windows_sys::Win32::Networking::WinSock::AF_INET;

#[cfg(windows)]
use windows_sys::Win32::Security::Cryptography::{
    BCryptGenRandom, BCRYPT_USE_SYSTEM_PREFERRED_RNG,
};

const ENGINE_ID: &str = "llama.cpp";
const MAX_LOG_BYTES: usize = 256 * 1024;
const MAX_LOG_LINES: usize = 200;
const MAX_PROBE_BYTES: usize = 64 * 1024;
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
    api_key_handle: Option<File>,
    credential: String,
    port: u16,
    runtime_instance_id: String,
    runtime_instance_fingerprint: String,
    binding_fingerprint: String,
    model_id: String,
    model_display_name: String,
    _model_handle: File,
    _runtime_handles: Vec<File>,
    _directory_handles: Vec<File>,
    _state_directory_handles: Vec<File>,
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

    pub fn status(&self, bridge: &ControlPlaneBridge) -> ManagedRuntimeStatus {
        let _lifecycle = self
            .lifecycle
            .lock()
            .expect("managed runtime lifecycle lock poisoned");
        let exited = {
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if inner
                .active
                .as_ref()
                .is_some_and(|active| !active.process.is_running())
            {
                let active = inner.active.take();
                inner.state = ManagedRuntimeState::Failed;
                inner.runtime_version = None;
                inner.last_error = Some("managed runtime exited".into());
                active
            } else {
                None
            }
        };
        if let Some(active) = exited {
            let _ = bridge.request(ControlPlaneMethod::ModelManagedDetach, json!({}));
            Self::dispose_active(active, false);
        }

        let runtime_installed = self.artifacts.has_valid_runtime();
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
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
        if let Some(active) = inner.active.take() {
            Self::dispose_active(active, true);
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
        let launch = self.artifacts.resolve_launch(model_id)?;
        verify_runtime_capabilities(&launch)?;
        let state_directory_handles = self.artifacts.guard_runtime_state_root()?;
        let credential = generate_credential()?;
        let port = select_ephemeral_loopback_port()?;
        let (api_key_file, api_key_handle) =
            write_private_api_key_file(&roots.state_root, &credential)?;
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
                drop(api_key_handle);
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

        let ready = wait_ready(&process, port, &credential, &alias, STARTUP_TIMEOUT);
        if let Err(error) = ready {
            process.terminate(1);
            let _ = process.wait_bounded(3000);
            if let Some(handle) = stdout_reader.take() {
                let _ = handle.join();
            }
            if let Some(handle) = stderr_reader.take() {
                let _ = handle.join();
            }
            drop(api_key_handle);
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
            api_key_handle: Some(api_key_handle),
            credential,
            port,
            runtime_instance_id,
            runtime_instance_fingerprint,
            binding_fingerprint,
            model_id: launch.model_id,
            model_display_name: launch.model_display_name,
            _model_handle: launch.model_handle,
            _runtime_handles: launch.runtime_handles,
            _directory_handles: launch.directory_handles,
            _state_directory_handles: state_directory_handles,
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

    fn dispose_active(mut active: ActiveRuntime, terminate: bool) {
        if terminate && active.process.is_running() {
            active.process.terminate(0);
        }
        let _ = active.process.wait_bounded(3000);
        if let Some(handle) = active.stdout_reader.take() {
            let _ = handle.join();
        }
        if let Some(handle) = active.stderr_reader.take() {
            let _ = handle.join();
        }
        drop(active.api_key_handle.take());
        let _ = fs::remove_file(&active.api_key_file);
        active.credential.clear();
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
            if let Some(active) = inner.active.take() {
                Self::dispose_active(active, true);
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
    let stdout_reader = process.take_stdout().map(spawn_probe_reader);
    let stderr_reader = process.take_stderr().map(spawn_probe_reader);
    let completed = process.wait_bounded(5000);
    if !completed {
        process.terminate(1);
        let _ = process.wait_bounded(3000);
    }
    let stdout = join_probe_reader(stdout_reader)?;
    let stderr = join_probe_reader(stderr_reader)?;
    if !completed {
        return Err(ManagedRuntimeError::new(
            "runtime_incompatible",
            "runtime probe timed out",
        ));
    }
    if stdout.overflow || stderr.overflow {
        return Err(ManagedRuntimeError::new(
            "runtime_incompatible",
            "runtime probe output too large",
        ));
    }
    let mut output = String::from_utf8_lossy(&stdout.bytes).into_owned();
    if !stderr.bytes.is_empty() {
        if !output.is_empty() {
            output.push('\n');
        }
        output.push_str(&String::from_utf8_lossy(&stderr.bytes));
    }
    Ok(sanitize_text(&output, MAX_PROBE_BYTES))
}

struct ProbeOutput {
    bytes: Vec<u8>,
    overflow: bool,
}

fn spawn_probe_reader(mut file: File) -> thread::JoinHandle<ProbeOutput> {
    thread::Builder::new()
        .name("localcomet-runtime-probe-log".into())
        .spawn(move || {
            let mut output = ProbeOutput {
                bytes: Vec::new(),
                overflow: false,
            };
            let mut buffer = [0_u8; 4096];
            while let Ok(count) = file.read(&mut buffer) {
                if count == 0 {
                    break;
                }
                let remaining = MAX_PROBE_BYTES.saturating_sub(output.bytes.len());
                let retained = remaining.min(count);
                output.bytes.extend_from_slice(&buffer[..retained]);
                output.overflow |= retained < count;
            }
            output
        })
        .expect("runtime probe reader spawn failed")
}

fn join_probe_reader(
    reader: Option<thread::JoinHandle<ProbeOutput>>,
) -> Result<ProbeOutput, ManagedRuntimeError> {
    match reader {
        Some(handle) => handle
            .join()
            .map_err(|_| ManagedRuntimeError::new("runtime_incompatible", "probe reader failed")),
        None => Ok(ProbeOutput {
            bytes: Vec::new(),
            overflow: false,
        }),
    }
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
    process: &ContainedManagedRuntimeProcess,
    port: u16,
    credential: &str,
    expected_alias: &str,
    timeout: Duration,
) -> Result<(), ManagedRuntimeError> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if !process.is_running() {
            return Err(ManagedRuntimeError::new(
                "runtime_exited",
                "managed runtime exited before readiness",
            ));
        }
        match http_get_json(port, "/health", credential) {
            Ok(value) if health_payload_ready(&value)? => {
                if !loopback_listener_owned_by_process(port, process.process_id())? {
                    return Err(ManagedRuntimeError::new(
                        "endpoint_owner_mismatch",
                        "managed endpoint owner mismatch",
                    ));
                }
                let models = http_get_json(port, "/v1/models", credential)?;
                if model_list_contains_exact_alias(&models, expected_alias)? {
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
    let mut response = Vec::new();
    stream
        .take(65_537)
        .read_to_end(&mut response)
        .map_err(|_| {
            ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint read failed")
        })?;
    if response.len() > 65_536 {
        return Err(ManagedRuntimeError::new(
            "invalid_payload",
            "managed endpoint response too large",
        ));
    }
    let separator = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "HTTP header rejected"))?;
    let header = std::str::from_utf8(&response[..separator]).map_err(|_| {
        ManagedRuntimeError::new("invalid_payload", "HTTP header encoding rejected")
    })?;
    let body = &response[separator + 4..];
    let mut lines = header.split("\r\n");
    let status_line = lines
        .next()
        .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "HTTP status missing"))?;
    let mut status_parts = status_line.split_ascii_whitespace();
    let protocol = status_parts.next().unwrap_or_default();
    let status = status_parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "HTTP status rejected"))?;
    if !matches!(protocol, "HTTP/1.0" | "HTTP/1.1") || status_parts.next().is_none() {
        return Err(ManagedRuntimeError::new(
            "invalid_payload",
            "HTTP status rejected",
        ));
    }
    if (300..400).contains(&status) {
        return Err(ManagedRuntimeError::new(
            "invalid_payload",
            "redirect rejected",
        ));
    }
    if status != 200 {
        return Err(ManagedRuntimeError::new(
            "sidecar_unavailable",
            "managed endpoint non-200",
        ));
    }
    let mut content_length = None;
    for line in lines {
        let (name, value) = line
            .split_once(':')
            .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "HTTP header rejected"))?;
        if name.eq_ignore_ascii_case("transfer-encoding") {
            return Err(ManagedRuntimeError::new(
                "invalid_payload",
                "HTTP transfer encoding rejected",
            ));
        }
        if name.eq_ignore_ascii_case("content-length") {
            if content_length.is_some() {
                return Err(ManagedRuntimeError::new(
                    "invalid_payload",
                    "duplicate content length rejected",
                ));
            }
            content_length = Some(value.trim().parse::<usize>().map_err(|_| {
                ManagedRuntimeError::new("invalid_payload", "content length rejected")
            })?);
        }
    }
    if content_length.is_some_and(|expected| expected != body.len()) {
        return Err(ManagedRuntimeError::new(
            "invalid_payload",
            "HTTP body length mismatch",
        ));
    }
    std::str::from_utf8(body)
        .map(str::to_owned)
        .map_err(|_| ManagedRuntimeError::new("invalid_payload", "JSON encoding rejected"))
}

fn health_payload_ready(body: &str) -> Result<bool, ManagedRuntimeError> {
    let value: Value = serde_json::from_str(body)
        .map_err(|_| ManagedRuntimeError::new("invalid_payload", "health JSON rejected"))?;
    let object = value
        .as_object()
        .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "health payload rejected"))?;
    let status = object
        .get("status")
        .and_then(Value::as_str)
        .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "health status rejected"))?;
    match status {
        "ok" => Ok(true),
        "loading model" => Ok(false),
        _ => Err(ManagedRuntimeError::new(
            "invalid_payload",
            "health status rejected",
        )),
    }
}

fn model_list_contains_exact_alias(
    body: &str,
    expected_alias: &str,
) -> Result<bool, ManagedRuntimeError> {
    let value: Value = serde_json::from_str(body)
        .map_err(|_| ManagedRuntimeError::new("invalid_payload", "model list JSON rejected"))?;
    let data = value
        .as_object()
        .and_then(|object| object.get("data"))
        .and_then(Value::as_array)
        .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "model list rejected"))?;
    if data.is_empty() || data.len() > 32 {
        return Err(ManagedRuntimeError::new(
            "invalid_payload",
            "model list size rejected",
        ));
    }
    let mut found = false;
    for entry in data {
        let model_id = entry
            .as_object()
            .and_then(|object| object.get("id"))
            .and_then(Value::as_str)
            .ok_or_else(|| ManagedRuntimeError::new("invalid_payload", "model entry rejected"))?;
        if model_id.len() > 128 || model_id.chars().any(char::is_control) {
            return Err(ManagedRuntimeError::new(
                "invalid_payload",
                "model alias rejected",
            ));
        }
        found |= model_id == expected_alias;
    }
    Ok(found)
}

#[cfg(windows)]
fn loopback_listener_owned_by_process(
    port: u16,
    process_id: u32,
) -> Result<bool, ManagedRuntimeError> {
    const MAX_TCP_TABLE_BYTES: u32 = 16 * 1024 * 1024;
    let mut table_bytes = 0_u32;
    let initial = unsafe {
        GetExtendedTcpTable(
            std::ptr::null_mut(),
            &mut table_bytes,
            0,
            AF_INET as u32,
            TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
    };
    if initial != ERROR_INSUFFICIENT_BUFFER && initial != NO_ERROR {
        return Err(ManagedRuntimeError::new(
            "endpoint_owner_unavailable",
            "TCP ownership query failed",
        ));
    }
    if table_bytes < std::mem::size_of::<u32>() as u32 || table_bytes > MAX_TCP_TABLE_BYTES {
        return Err(ManagedRuntimeError::new(
            "endpoint_owner_unavailable",
            "TCP ownership table size rejected",
        ));
    }
    let capacity = table_bytes
        .saturating_add(64 * 1024)
        .min(MAX_TCP_TABLE_BYTES);
    let mut buffer = vec![0_u8; capacity as usize];
    table_bytes = capacity;
    let result = unsafe {
        GetExtendedTcpTable(
            buffer.as_mut_ptr().cast(),
            &mut table_bytes,
            0,
            AF_INET as u32,
            TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
    };
    if result != NO_ERROR || table_bytes as usize > buffer.len() {
        return Err(ManagedRuntimeError::new(
            "endpoint_owner_unavailable",
            "TCP ownership query failed",
        ));
    }
    let count = unsafe { std::ptr::read_unaligned(buffer.as_ptr().cast::<u32>()) } as usize;
    let row_offset = std::mem::size_of::<u32>();
    let row_bytes = std::mem::size_of::<MIB_TCPROW_OWNER_PID>();
    let maximum_rows = (table_bytes as usize).saturating_sub(row_offset) / row_bytes;
    if count > maximum_rows {
        return Err(ManagedRuntimeError::new(
            "endpoint_owner_unavailable",
            "TCP ownership table rejected",
        ));
    }
    let loopback = u32::from_ne_bytes([127, 0, 0, 1]);
    for index in 0..count {
        let row = unsafe {
            std::ptr::read_unaligned(
                buffer
                    .as_ptr()
                    .add(row_offset + index * row_bytes)
                    .cast::<MIB_TCPROW_OWNER_PID>(),
            )
        };
        let row_port = u16::from_be((row.dwLocalPort & 0xffff) as u16);
        if row.dwLocalAddr == loopback && row_port == port {
            return Ok(row.dwOwningPid == process_id);
        }
    }
    Ok(false)
}

#[cfg(not(windows))]
fn loopback_listener_owned_by_process(
    _port: u16,
    _process_id: u32,
) -> Result<bool, ManagedRuntimeError> {
    Err(ManagedRuntimeError::new(
        "endpoint_owner_unavailable",
        "Windows TCP ownership is required",
    ))
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
) -> Result<(PathBuf, File), ManagedRuntimeError> {
    let file_name = format!("key-{}.txt", hex_bytes(&random_bytes(16)?));
    let path = state_root.join(file_name);
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(windows)]
    options.share_mode(0x0000_0001);
    let mut file = options
        .open(&path)
        .map_err(|_| ManagedRuntimeError::new("io_error", "credential file creation failed"))?;
    file.write_all(credential.as_bytes())
        .and_then(|_| file.write_all(b"\n"))
        .and_then(|_| file.sync_all())
        .map_err(|_| ManagedRuntimeError::new("io_error", "credential file write failed"))?;
    Ok((path, file))
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
        let mut boundary = limit;
        while boundary > 0 && !text.is_char_boundary(boundary) {
            boundary -= 1;
        }
        text.truncate(boundary);
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
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
) -> ManagedRuntimeStatus {
    runtime.status(&bridge)
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

    #[test]
    fn readiness_payloads_require_exact_json_fields() {
        assert!(health_payload_ready(r#"{"status":"ok"}"#).expect("valid health"));
        assert!(
            !health_payload_ready(r#"{"status":"loading model"}"#).expect("valid loading health")
        );
        assert!(health_payload_ready(r#"{"message":"status ok"}"#).is_err());
        assert!(model_list_contains_exact_alias(
            r#"{"object":"list","data":[{"id":"expected"}]}"#,
            "expected"
        )
        .expect("valid model list"));
        assert!(!model_list_contains_exact_alias(
            r#"{"object":"list","data":[{"id":"expected-suffix"}]}"#,
            "expected"
        )
        .expect("valid nonmatching model list"));
        assert!(model_list_contains_exact_alias(r#"{"data":"expected"}"#, "expected").is_err());
    }

    #[cfg(windows)]
    #[test]
    fn loopback_listener_ownership_is_exact() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("bind loopback test listener");
        let port = listener.local_addr().expect("listener address").port();
        assert!(loopback_listener_owned_by_process(port, std::process::id())
            .expect("query listener owner"));
        assert!(
            !loopback_listener_owned_by_process(port, std::process::id().wrapping_add(1))
                .expect("query mismatched listener owner")
        );
    }
}
