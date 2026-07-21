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
use std::sync::atomic::{AtomicBool, Ordering};
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
const MAX_LOG_CARRY_BYTES: usize = 512 * 1024;
const MAX_PROBE_BYTES: usize = 64 * 1024;
const MODEL_LOAD_TIMEOUT: Duration = Duration::from_secs(300);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(5);
const PROCESS_DROP_WAIT_RESERVE: Duration = Duration::from_secs(2);
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

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub enum ManagedModelState {
    Unavailable,
    Validating,
    Loading,
    Ready,
    Failed,
    Unloading,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeStatus {
    pub engine: &'static str,
    pub state: ManagedRuntimeState,
    pub model_state: ManagedModelState,
    pub inference_ready: bool,
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
    pub model_state: ManagedModelState,
    pub inference_ready: bool,
    pub provider_id: &'static str,
    pub model_id: String,
    pub model_display_name: String,
    pub runtime_instance_id: String,
    pub runtime_instance_fingerprint: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeStopResponse {
    pub state: ManagedRuntimeState,
    pub model_state: ManagedModelState,
    pub inference_ready: bool,
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
    process: Arc<Mutex<ContainedManagedRuntimeProcess>>,
    startup_generation: u64,
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

#[derive(Clone)]
struct StartupAttempt {
    generation: u64,
    cancelled: Arc<AtomicBool>,
}

impl StartupAttempt {
    fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
    }

    fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::SeqCst)
    }

    fn ensure_active(&self) -> Result<(), ManagedRuntimeError> {
        if self.is_cancelled() {
            Err(ManagedRuntimeError::new(
                "start_cancelled",
                "managed runtime start was cancelled",
            ))
        } else {
            Ok(())
        }
    }
}

#[derive(Default, Debug)]
struct LogTail {
    bytes: usize,
    lines: Vec<String>,
}

struct ManagedRuntimeInner {
    state: ManagedRuntimeState,
    model_state: ManagedModelState,
    inference_ready: bool,
    runtime_version: Option<String>,
    last_error: Option<String>,
    active: Option<ActiveRuntime>,
    startup: Option<StartupAttempt>,
    next_startup_generation: u64,
    stdout_tail: Arc<Mutex<LogTail>>,
    stderr_tail: Arc<Mutex<LogTail>>,
}

impl Default for ManagedRuntimeInner {
    fn default() -> Self {
        Self {
            state: ManagedRuntimeState::NotInstalled,
            model_state: ManagedModelState::Unavailable,
            inference_ready: false,
            runtime_version: None,
            last_error: None,
            active: None,
            startup: None,
            next_startup_generation: 0,
            stdout_tail: Arc::new(Mutex::new(LogTail::default())),
            stderr_tail: Arc::new(Mutex::new(LogTail::default())),
        }
    }
}

pub struct ManagedRuntimeSupervisor {
    artifacts: Arc<ArtifactTrustService>,
    transition: Mutex<()>,
    inner: Mutex<ManagedRuntimeInner>,
}

impl ManagedRuntimeSupervisor {
    pub fn new(artifacts: Arc<ArtifactTrustService>) -> Self {
        Self {
            artifacts,
            transition: Mutex::new(()),
            inner: Mutex::new(ManagedRuntimeInner::default()),
        }
    }

    pub fn status(&self, bridge: &ControlPlaneBridge) -> ManagedRuntimeStatus {
        let exited = {
            let _transition = self
                .transition
                .lock()
                .expect("managed runtime transition lock poisoned");
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if inner
                .active
                .as_ref()
                .is_some_and(|active| !managed_process_is_running(&active.process))
            {
                let active = inner.active.take();
                if let Some(startup) = inner.startup.take() {
                    startup.cancel();
                }
                inner.state = ManagedRuntimeState::Stopping;
                inner.model_state = ManagedModelState::Unloading;
                inner.inference_ready = false;
                inner.runtime_version = None;
                inner.last_error = Some("managed runtime exited".into());
                active
            } else {
                None
            }
        };
        if let Some(active) = exited {
            let _ = bridge.request(ControlPlaneMethod::ModelManagedDetach, json!({}));
            Self::dispose_active(active, false, SHUTDOWN_TIMEOUT);
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if inner.state == ManagedRuntimeState::Stopping && inner.active.is_none() {
                inner.state = ManagedRuntimeState::Failed;
                inner.model_state = ManagedModelState::Failed;
                inner.inference_ready = false;
            }
        }

        let runtime_in_use = {
            let inner = self.inner.lock().expect("managed runtime lock poisoned");
            inner.active.is_some() || inner.startup.is_some()
        };
        let runtime_installed = runtime_in_use || self.artifacts.has_valid_runtime();
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        if inner.active.is_none() && !runtime_installed {
            inner.state = ManagedRuntimeState::NotInstalled;
            inner.model_state = ManagedModelState::Unavailable;
            inner.inference_ready = false;
        } else if inner.active.is_none() && inner.state == ManagedRuntimeState::NotInstalled {
            inner.state = ManagedRuntimeState::Stopped;
            inner.model_state = ManagedModelState::Unavailable;
            inner.inference_ready = false;
        }
        let active = inner.active.as_ref();
        ManagedRuntimeStatus {
            engine: ENGINE_ID,
            state: inner.state.clone(),
            model_state: inner.model_state.clone(),
            inference_ready: inner.inference_ready,
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

    pub(crate) fn ensure_model_ready(&self, model_id: &str) -> Result<(), BridgeError> {
        let _transition = self
            .transition
            .lock()
            .expect("managed runtime transition lock poisoned");
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        let process_running = inner
            .active
            .as_ref()
            .is_some_and(|active| managed_process_is_running(&active.process));
        if !process_running {
            if inner.active.is_some() {
                inner.state = ManagedRuntimeState::Failed;
                inner.model_state = ManagedModelState::Failed;
                inner.inference_ready = false;
                inner.last_error = Some("managed runtime exited".into());
            }
            return Err(ManagedRuntimeError::new(
                "runtime_not_ready",
                "managed runtime is not ready",
            )
            .into());
        }
        if inner.state != ManagedRuntimeState::Ready {
            return Err(ManagedRuntimeError::new(
                "runtime_not_ready",
                "managed runtime is not ready",
            )
            .into());
        }
        let model_ready = inner.model_state == ManagedModelState::Ready
            && inner.inference_ready
            && inner
                .active
                .as_ref()
                .is_some_and(|active| active.model_id == model_id);
        if !model_ready {
            return Err(
                ManagedRuntimeError::new("model_not_ready", "managed model is not ready").into(),
            );
        }
        Ok(())
    }

    pub fn start(
        &self,
        model_id: &str,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedRuntimeStartResponse, BridgeError> {
        let attempt = self.begin_start()?;
        let model_load_deadline = Instant::now() + MODEL_LOAD_TIMEOUT;
        let response = match self.start_inner(model_id, model_load_deadline, &attempt) {
            Ok(response) => response,
            Err(error) => {
                return Err(self.settle_start_failure(&attempt, error, bridge, false));
            }
        };
        let attach = match self.attach_payload_for_attempt(&attempt) {
            Ok(attach) => attach,
            Err(error) => {
                return Err(self.settle_start_failure(&attempt, error, bridge, false));
            }
        };
        let attach_response = remaining_model_load_timeout(model_load_deadline)
            .map_err(BridgeError::from)
            .and_then(|timeout| {
                bridge.request_with_timeout(ControlPlaneMethod::ModelManagedAttach, attach, timeout)
            })
            .and_then(|value| {
                validate_managed_attach_response(&value, &response).map_err(BridgeError::from)
            });
        if let Err(error) = attach_response {
            let error = normalize_managed_attach_error(error);
            return Err(self.settle_start_failure(&attempt, error, bridge, true));
        }
        match self.complete_start(&attempt) {
            Ok(()) => Ok(response),
            Err(error) => Err(self.settle_start_failure(&attempt, error, bridge, true)),
        }
    }

    pub fn stop(
        &self,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedRuntimeStopResponse, BridgeError> {
        let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
        let (active, final_state) = {
            let _transition = self
                .transition
                .lock()
                .expect("managed runtime transition lock poisoned");
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if inner.state == ManagedRuntimeState::Stopping {
                return Err(ManagedRuntimeError::new("busy", "managed runtime is stopping").into());
            }
            let final_state = if inner.state == ManagedRuntimeState::NotInstalled {
                ManagedRuntimeState::NotInstalled
            } else {
                ManagedRuntimeState::Stopped
            };
            if let Some(startup) = inner.startup.take() {
                startup.cancel();
            }
            inner.state = ManagedRuntimeState::Stopping;
            inner.model_state = ManagedModelState::Unloading;
            inner.inference_ready = false;
            inner.last_error = None;
            (inner.active.take(), final_state)
        };

        let detach_result = remaining_shutdown_timeout(deadline).and_then(|timeout| {
            bridge.request_with_timeout(
                ControlPlaneMethod::ModelManagedDetach,
                json!({}),
                timeout.min(Duration::from_secs(2)),
            )
        });
        if let Some(active) = active {
            Self::dispose_active(
                active,
                true,
                deadline.saturating_duration_since(Instant::now()),
            );
        }
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        inner.runtime_version = None;
        inner.state = final_state;
        inner.model_state = ManagedModelState::Unavailable;
        inner.inference_ready = false;
        let response = ManagedRuntimeStopResponse {
            state: inner.state.clone(),
            model_state: inner.model_state.clone(),
            inference_ready: false,
            stopped: true,
        };
        if detach_result.is_err() {
            inner.last_error = Some("managed provider detach failed".into());
            return Err(ManagedRuntimeError::new(
                "shutdown_failed",
                "managed provider detach failed; runtime process was stopped",
            )
            .into());
        }
        inner.last_error = None;
        Ok(response)
    }

    fn begin_start(&self) -> Result<StartupAttempt, BridgeError> {
        let _transition = self
            .transition
            .lock()
            .expect("managed runtime transition lock poisoned");
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        if inner.active.is_some()
            || inner.startup.is_some()
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
        inner.next_startup_generation = inner.next_startup_generation.wrapping_add(1).max(1);
        let attempt = StartupAttempt {
            generation: inner.next_startup_generation,
            cancelled: Arc::new(AtomicBool::new(false)),
        };
        inner.startup = Some(attempt.clone());
        inner.state = ManagedRuntimeState::Validating;
        inner.model_state = ManagedModelState::Validating;
        inner.inference_ready = false;
        inner.runtime_version = None;
        inner.last_error = None;
        Ok(attempt)
    }

    fn start_inner(
        &self,
        model_id: &str,
        model_load_deadline: Instant,
        attempt: &StartupAttempt,
    ) -> Result<ManagedRuntimeStartResponse, BridgeError> {
        let roots = self.artifacts.roots();
        let launch = self.artifacts.resolve_launch(model_id)?;
        attempt.ensure_active()?;
        verify_runtime_capabilities(&launch, attempt)?;
        attempt.ensure_active()?;
        let state_directory_handles = self.artifacts.guard_runtime_state_root()?;
        let credential = generate_credential()?;
        let port = select_ephemeral_loopback_port()?;
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
        let response = ManagedRuntimeStartResponse {
            state: ManagedRuntimeState::Ready,
            model_state: ManagedModelState::Ready,
            inference_ready: true,
            provider_id: "managed-llama-cpp",
            model_id: launch.model_id.clone(),
            model_display_name: launch.model_display_name.clone(),
            runtime_instance_id: runtime_instance_id.clone(),
            runtime_instance_fingerprint: runtime_instance_fingerprint.clone(),
        };

        let process = {
            let _transition = self
                .transition
                .lock()
                .expect("managed runtime transition lock poisoned");
            {
                let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
                if !startup_is_current(&inner, attempt) || attempt.is_cancelled() {
                    return Err(ManagedRuntimeError::new(
                        "start_cancelled",
                        "managed runtime start was cancelled",
                    )
                    .into());
                }
                inner.state = ManagedRuntimeState::Starting;
                inner.model_state = ManagedModelState::Loading;
                inner.inference_ready = false;
            }
            let (api_key_file, api_key_handle) =
                write_private_api_key_file(&roots.state_root, &credential)?;
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
            let mut stdout_reader = None;
            if let Some(stdout) = process.take_stdout() {
                match spawn_log_reader(
                    stdout,
                    stdout_tail,
                    self.redaction_markers(&credential, &api_key_file),
                ) {
                    Ok(reader) => stdout_reader = Some(reader),
                    Err(_) => {
                        process.terminate(1);
                        let _ = process.wait_bounded(3000);
                        drop(api_key_handle);
                        let _ = fs::remove_file(&api_key_file);
                        return Err(ManagedRuntimeError::new(
                            "launch_failed",
                            "managed runtime log reader could not start",
                        )
                        .into());
                    }
                }
            }
            let stderr_reader = if let Some(stderr) = process.take_stderr() {
                match spawn_log_reader(
                    stderr,
                    stderr_tail,
                    self.redaction_markers(&credential, &api_key_file),
                ) {
                    Ok(reader) => Some(reader),
                    Err(_) => {
                        process.terminate(1);
                        let _ = process.wait_bounded(3000);
                        if let Some(reader) = stdout_reader.take() {
                            join_reader_bounded(reader, Instant::now() + Duration::from_secs(1));
                        }
                        drop(api_key_handle);
                        let _ = fs::remove_file(&api_key_file);
                        return Err(ManagedRuntimeError::new(
                            "launch_failed",
                            "managed runtime log reader could not start",
                        )
                        .into());
                    }
                }
            } else {
                None
            };
            let process = Arc::new(Mutex::new(process));
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if !startup_is_current(&inner, attempt) || attempt.is_cancelled() {
                drop(inner);
                let active = ActiveRuntime {
                    process,
                    startup_generation: attempt.generation,
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
                };
                Self::dispose_active(active, true, SHUTDOWN_TIMEOUT);
                return Err(ManagedRuntimeError::new(
                    "start_cancelled",
                    "managed runtime start was cancelled",
                )
                .into());
            }
            inner.runtime_version = Some(launch.runtime_release_tag);
            inner.active = Some(ActiveRuntime {
                process: Arc::clone(&process),
                startup_generation: attempt.generation,
                stdout_reader,
                stderr_reader,
                api_key_file,
                api_key_handle: Some(api_key_handle),
                credential: credential.clone(),
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
            process
        };

        remaining_model_load_timeout(model_load_deadline).and_then(|timeout| {
            wait_ready(
                &process,
                port,
                &credential,
                &alias,
                timeout,
                &attempt.cancelled,
            )
        })?;
        Ok(response)
    }

    fn attach_payload_for_attempt(&self, attempt: &StartupAttempt) -> Result<Value, BridgeError> {
        let inner = self.inner.lock().expect("managed runtime lock poisoned");
        if !startup_is_current(&inner, attempt) || attempt.is_cancelled() {
            return Err(ManagedRuntimeError::new(
                "start_cancelled",
                "managed runtime start was cancelled",
            )
            .into());
        }
        let active = inner.active.as_ref().ok_or_else(|| {
            ManagedRuntimeError::new("sidecar_unavailable", "managed runtime is not active")
        })?;
        if active.startup_generation != attempt.generation {
            return Err(ManagedRuntimeError::new(
                "start_cancelled",
                "managed runtime start was superseded",
            )
            .into());
        }
        Ok(json!({
            "runtime_instance_id": active.runtime_instance_id,
            "port": active.port,
            "credential": active.credential,
            "expected_model_alias": safe_alias(&active.model_id),
            "model_id": active.model_id,
            "binding_fingerprint": active.binding_fingerprint,
        }))
    }

    fn complete_start(&self, attempt: &StartupAttempt) -> Result<(), BridgeError> {
        let _transition = self
            .transition
            .lock()
            .expect("managed runtime transition lock poisoned");
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        let process_ready = inner.active.as_ref().is_some_and(|active| {
            active.startup_generation == attempt.generation
                && managed_process_is_running(&active.process)
        });
        if !startup_is_current(&inner, attempt) || attempt.is_cancelled() || !process_ready {
            return Err(ManagedRuntimeError::new(
                "start_cancelled",
                "managed runtime start was cancelled",
            )
            .into());
        }
        inner.startup = None;
        inner.state = ManagedRuntimeState::Ready;
        inner.model_state = ManagedModelState::Ready;
        inner.inference_ready = true;
        inner.last_error = None;
        Ok(())
    }

    fn settle_start_failure(
        &self,
        attempt: &StartupAttempt,
        error: BridgeError,
        bridge: &ControlPlaneBridge,
        detach_attempted: bool,
    ) -> BridgeError {
        let process = {
            let _transition = self
                .transition
                .lock()
                .expect("managed runtime transition lock poisoned");
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if !startup_is_current(&inner, attempt) {
                return ManagedRuntimeError::new(
                    "start_cancelled",
                    "managed runtime start was cancelled",
                )
                .into();
            }
            inner.startup = None;
            inner.state = ManagedRuntimeState::Failed;
            inner.model_state = ManagedModelState::Failed;
            inner.inference_ready = false;
            inner.runtime_version = None;
            inner.last_error = Some(sanitize_text(&error.message, 240));
            inner
                .active
                .as_ref()
                .filter(|active| active.startup_generation == attempt.generation)
                .map(|active| Arc::clone(&active.process))
        };
        if let Some(process) = process {
            terminate_managed_process(&process, 1);
        }

        let cleanup_deadline = Instant::now() + SHUTDOWN_TIMEOUT;
        if detach_attempted {
            if let Ok(timeout) = remaining_shutdown_timeout(cleanup_deadline) {
                let _ = bridge.request_with_timeout(
                    ControlPlaneMethod::ModelManagedDetach,
                    json!({}),
                    timeout.min(Duration::from_secs(2)),
                );
            }
        }
        let active = {
            let _transition = self
                .transition
                .lock()
                .expect("managed runtime transition lock poisoned");
            let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
            if inner
                .active
                .as_ref()
                .is_some_and(|active| active.startup_generation == attempt.generation)
            {
                inner.active.take()
            } else {
                None
            }
        };
        if let Some(active) = active {
            Self::dispose_active(
                active,
                true,
                cleanup_deadline.saturating_duration_since(Instant::now()),
            );
        }
        error
    }

    fn dispose_active(mut active: ActiveRuntime, terminate: bool, timeout: Duration) {
        let cleanup_budget = timeout
            .min(SHUTDOWN_TIMEOUT)
            .saturating_sub(PROCESS_DROP_WAIT_RESERVE);
        let deadline = Instant::now() + cleanup_budget;
        {
            let process = active
                .process
                .lock()
                .expect("managed runtime process lock poisoned");
            if terminate && process.is_running() {
                process.terminate(0);
            }
            let _ = process.wait_bounded(remaining_millis(deadline).min(3_000));
        }
        if let Some(handle) = active.stdout_reader.take() {
            join_reader_bounded(handle, deadline);
        }
        if let Some(handle) = active.stderr_reader.take() {
            join_reader_bounded(handle, deadline);
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
        let active = if let Ok(mut inner) = self.inner.lock() {
            if let Some(startup) = inner.startup.take() {
                startup.cancel();
            }
            inner.active.take()
        } else {
            None
        };
        if let Some(active) = active {
            Self::dispose_active(active, true, SHUTDOWN_TIMEOUT);
        }
    }
}

fn startup_is_current(inner: &ManagedRuntimeInner, attempt: &StartupAttempt) -> bool {
    inner
        .startup
        .as_ref()
        .is_some_and(|startup| startup.generation == attempt.generation)
}

fn managed_process_is_running(process: &Arc<Mutex<ContainedManagedRuntimeProcess>>) -> bool {
    process
        .lock()
        .expect("managed runtime process lock poisoned")
        .is_running()
}

fn terminate_managed_process(process: &Arc<Mutex<ContainedManagedRuntimeProcess>>, exit_code: u32) {
    let process = process
        .lock()
        .expect("managed runtime process lock poisoned");
    if process.is_running() {
        process.terminate(exit_code);
    }
}

fn validate_managed_attach_response(
    response: &Value,
    expected: &ManagedRuntimeStartResponse,
) -> Result<(), ManagedRuntimeError> {
    let object = response.as_object().ok_or_else(|| {
        ManagedRuntimeError::new("model_load_failed", "managed attach response rejected")
    })?;
    if object.get("provider_id").and_then(Value::as_str) != Some("managed-llama-cpp")
        || object.get("runtime_instance_id").and_then(Value::as_str)
            != Some(expected.runtime_instance_id.as_str())
        || object.get("model_id").and_then(Value::as_str) != Some(expected.model_id.as_str())
        || object.get("model_state").and_then(Value::as_str) != Some("Ready")
        || object.get("attached").and_then(Value::as_bool) != Some(true)
        || object.get("inference_ready").and_then(Value::as_bool) != Some(true)
    {
        return Err(ManagedRuntimeError::new(
            "model_load_failed",
            "managed attach identity or inference readiness mismatch",
        ));
    }
    Ok(())
}

fn normalize_managed_attach_error(error: BridgeError) -> BridgeError {
    let code = match error.code.as_str() {
        "timeout"
        | "model_load_timed_out"
        | "first_token_timeout"
        | "inactivity_timeout"
        | "overall_timeout" => "model_load_timed_out",
        _ => "model_load_failed",
    };
    ManagedRuntimeError::new(
        code,
        if code == "model_load_timed_out" {
            "approved model inference readiness timed out"
        } else {
            "approved model inference readiness failed"
        },
    )
    .into()
}

fn remaining_model_load_timeout(deadline: Instant) -> Result<Duration, ManagedRuntimeError> {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if remaining.is_zero() {
        Err(ManagedRuntimeError::new(
            "model_load_timed_out",
            "approved model load timed out",
        ))
    } else {
        Ok(remaining.min(MODEL_LOAD_TIMEOUT))
    }
}

fn remaining_shutdown_timeout(deadline: Instant) -> Result<Duration, BridgeError> {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if remaining.is_zero() {
        Err(BridgeError::new(
            "shutdown_failed",
            "managed runtime shutdown timed out",
        ))
    } else {
        Ok(remaining.min(SHUTDOWN_TIMEOUT))
    }
}

fn remaining_millis(deadline: Instant) -> u32 {
    deadline
        .saturating_duration_since(Instant::now())
        .as_millis()
        .min(u128::from(u32::MAX)) as u32
}

fn join_reader_bounded(handle: thread::JoinHandle<()>, deadline: Instant) {
    while !handle.is_finished() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(10));
    }
    if handle.is_finished() {
        let _ = handle.join();
    }
}

fn verify_runtime_capabilities(
    runtime: &ValidatedRuntimeModel,
    attempt: &StartupAttempt,
) -> Result<(), ManagedRuntimeError> {
    attempt.ensure_active()?;
    let version_output = run_capability_probe(runtime, "--version", attempt)?;
    if version_output.len() > 4096 {
        return Err(ManagedRuntimeError::new(
            "runtime_incompatible",
            "runtime version output too large",
        ));
    }
    attempt.ensure_active()?;
    let help_output = run_capability_probe(runtime, "--help", attempt)?;
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
    attempt: &StartupAttempt,
) -> Result<String, ManagedRuntimeError> {
    let spec = ManagedRuntimeLaunchSpec {
        executable: runtime.executable.clone(),
        args: vec![OsString::from(flag)],
        current_dir: runtime.package_dir.clone(),
        env: sanitized_runtime_environment(),
    };
    let mut process = ContainedManagedRuntimeProcess::spawn(&spec)
        .map_err(|_| ManagedRuntimeError::new("runtime_incompatible", "runtime probe failed"))?;
    let stdout_reader = match process.take_stdout() {
        Some(stdout) => Some(spawn_probe_reader(stdout).map_err(|_| {
            ManagedRuntimeError::new("runtime_incompatible", "probe reader could not start")
        })?),
        None => None,
    };
    let stderr_reader = match process.take_stderr() {
        Some(stderr) => match spawn_probe_reader(stderr) {
            Ok(reader) => Some(reader),
            Err(_) => {
                process.terminate(1);
                let _ = process.wait_bounded(3000);
                let _ = join_probe_reader(stdout_reader, Instant::now() + Duration::from_secs(1));
                return Err(ManagedRuntimeError::new(
                    "runtime_incompatible",
                    "probe reader could not start",
                ));
            }
        },
        None => None,
    };
    let deadline = Instant::now() + Duration::from_secs(5);
    let mut completed = false;
    while Instant::now() < deadline && !attempt.is_cancelled() {
        if process.wait_bounded(50) {
            completed = true;
            break;
        }
    }
    if !completed {
        process.terminate(1);
        let _ = process.wait_bounded(3000);
    }
    let stdout = join_probe_reader(stdout_reader, deadline)?;
    let stderr = join_probe_reader(stderr_reader, deadline)?;
    attempt.ensure_active()?;
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
    Ok(normalize_probe_output(output))
}

fn normalize_probe_output(output: String) -> String {
    output.replace('\0', "")
}

struct ProbeOutput {
    bytes: Vec<u8>,
    overflow: bool,
}

fn spawn_probe_reader(mut file: File) -> std::io::Result<thread::JoinHandle<ProbeOutput>> {
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
}

fn join_probe_reader(
    reader: Option<thread::JoinHandle<ProbeOutput>>,
    deadline: Instant,
) -> Result<ProbeOutput, ManagedRuntimeError> {
    match reader {
        Some(handle) => {
            while !handle.is_finished() && Instant::now() < deadline {
                thread::sleep(Duration::from_millis(10));
            }
            if !handle.is_finished() {
                return Err(ManagedRuntimeError::new(
                    "runtime_incompatible",
                    "probe reader timed out",
                ));
            }
            handle.join().map_err(|_| {
                ManagedRuntimeError::new("runtime_incompatible", "probe reader failed")
            })
        }
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
    process: &Arc<Mutex<ContainedManagedRuntimeProcess>>,
    port: u16,
    credential: &str,
    expected_alias: &str,
    timeout: Duration,
    cancelled: &AtomicBool,
) -> Result<(), ManagedRuntimeError> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if cancelled.load(Ordering::SeqCst) {
            return Err(ManagedRuntimeError::new(
                "start_cancelled",
                "managed runtime start was cancelled",
            ));
        }
        let (running, process_id) = {
            let process = process
                .lock()
                .expect("managed runtime process lock poisoned");
            (process.is_running(), process.process_id())
        };
        if !running {
            return Err(ManagedRuntimeError::new(
                "runtime_exited",
                "managed runtime exited before readiness",
            ));
        }
        match loopback_listener_owner(port)? {
            None => {
                sleep_until_cancelled(
                    cancelled,
                    Duration::from_millis(250)
                        .min(deadline.saturating_duration_since(Instant::now())),
                );
                continue;
            }
            Some(owner) if owner != process_id => {
                return Err(ManagedRuntimeError::new(
                    "endpoint_owner_mismatch",
                    "managed endpoint owner mismatch",
                ));
            }
            Some(_) => {}
        }
        match http_get_json(port, "/health", credential, process_id, deadline) {
            Ok(value) if health_payload_ready(&value)? => {
                if !loopback_listener_owned_by_process(port, process_id)? {
                    return Err(ManagedRuntimeError::new(
                        "endpoint_owner_mismatch",
                        "managed endpoint owner mismatch",
                    ));
                }
                let models = http_get_json(port, "/v1/models", credential, process_id, deadline)?;
                if model_list_contains_exact_alias(&models, expected_alias)? {
                    return Ok(());
                }
                return Err(ManagedRuntimeError::new(
                    "wrong_model",
                    "managed model alias mismatch",
                ));
            }
            _ => sleep_until_cancelled(
                cancelled,
                Duration::from_millis(250).min(deadline.saturating_duration_since(Instant::now())),
            ),
        }
    }
    Err(ManagedRuntimeError::new(
        "model_load_timed_out",
        "approved model load timed out",
    ))
}

fn sleep_until_cancelled(cancelled: &AtomicBool, duration: Duration) {
    let deadline = Instant::now() + duration;
    while !cancelled.load(Ordering::SeqCst) && Instant::now() < deadline {
        thread::sleep(
            Duration::from_millis(25).min(deadline.saturating_duration_since(Instant::now())),
        );
    }
}

fn http_get_json(
    port: u16,
    path: &str,
    credential: &str,
    expected_process_id: u32,
    deadline: Instant,
) -> Result<String, ManagedRuntimeError> {
    let timeout = deadline
        .saturating_duration_since(Instant::now())
        .min(Duration::from_secs(2));
    if timeout.is_zero() {
        return Err(ManagedRuntimeError::new(
            "model_load_timed_out",
            "approved model load timed out",
        ));
    }
    let address = std::net::SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, timeout).map_err(|_| {
        ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint unavailable")
    })?;
    if !loopback_listener_owned_by_process(port, expected_process_id)? {
        return Err(ManagedRuntimeError::new(
            "endpoint_owner_mismatch",
            "managed endpoint owner mismatch",
        ));
    }
    stream
        .set_read_timeout(Some(timeout))
        .map_err(|_| ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint timeout"))?;
    let write_timeout = deadline
        .saturating_duration_since(Instant::now())
        .min(Duration::from_secs(2));
    if write_timeout.is_zero() {
        return Err(ManagedRuntimeError::new(
            "model_load_timed_out",
            "approved model load timed out",
        ));
    }
    stream
        .set_write_timeout(Some(write_timeout))
        .map_err(|_| ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint timeout"))?;
    let request = format!(
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {credential}\r\nConnection: close\r\nAccept: application/json\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).map_err(|_| {
        ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint write failed")
    })?;
    let mut response = Vec::new();
    let mut chunk = [0_u8; 4096];
    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Err(ManagedRuntimeError::new(
                "model_load_timed_out",
                "approved model load timed out",
            ));
        }
        stream
            .set_read_timeout(Some(remaining.min(Duration::from_secs(2))))
            .map_err(|_| {
                ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint timeout")
            })?;
        let count = stream.read(&mut chunk).map_err(|_| {
            ManagedRuntimeError::new("sidecar_unavailable", "managed endpoint read failed")
        })?;
        if count == 0 {
            break;
        }
        response.extend_from_slice(&chunk[..count]);
        if response.len() > 65_536 {
            return Err(ManagedRuntimeError::new(
                "invalid_payload",
                "managed endpoint response too large",
            ));
        }
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
fn loopback_listener_owner(port: u16) -> Result<Option<u32>, ManagedRuntimeError> {
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
            return Ok(Some(row.dwOwningPid));
        }
    }
    Ok(None)
}

#[cfg(not(windows))]
fn loopback_listener_owner(_port: u16) -> Result<Option<u32>, ManagedRuntimeError> {
    Err(ManagedRuntimeError::new(
        "endpoint_owner_unavailable",
        "Windows TCP ownership is required",
    ))
}

fn loopback_listener_owned_by_process(
    port: u16,
    process_id: u32,
) -> Result<bool, ManagedRuntimeError> {
    Ok(loopback_listener_owner(port)? == Some(process_id))
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
    let write_result = file
        .write_all(credential.as_bytes())
        .and_then(|_| file.write_all(b"\n"))
        .and_then(|_| file.sync_all());
    if write_result.is_err() {
        drop(file);
        let _ = fs::remove_file(&path);
        return Err(ManagedRuntimeError::new(
            "io_error",
            "credential file write failed",
        ));
    }
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
) -> std::io::Result<thread::JoinHandle<()>> {
    thread::Builder::new()
        .name("localcomet-managed-runtime-log".into())
        .spawn(move || {
            let mut buffer = [0_u8; 1024];
            let mut carry = Vec::new();
            while let Ok(count) = file.read(&mut buffer) {
                if count == 0 {
                    break;
                }
                let mut guard = tail.lock().expect("managed log tail poisoned");
                consume_log_bytes(&mut carry, &buffer[..count], false, &markers, &mut guard);
            }
            let mut guard = tail.lock().expect("managed log tail poisoned");
            consume_log_bytes(&mut carry, &[], true, &markers, &mut guard);
        })
}

fn consume_log_bytes(
    carry: &mut Vec<u8>,
    incoming: &[u8],
    eof: bool,
    markers: &[(String, String)],
    tail: &mut LogTail,
) {
    carry.extend_from_slice(incoming);
    while let Some(newline) = carry.iter().position(|byte| *byte == b'\n') {
        let line: Vec<u8> = carry.drain(..=newline).collect();
        push_redacted_log_line(&line, markers, tail);
    }
    while carry.len() > MAX_LOG_CARRY_BYTES {
        let reserve = markers
            .iter()
            .map(|(needle, _)| needle.len().saturating_sub(1))
            .max()
            .unwrap_or(0)
            .min(MAX_LOG_CARRY_BYTES / 2);
        let mut split = carry.len().saturating_sub(reserve);
        loop {
            let mut adjusted = split;
            for (needle, _) in markers {
                let needle = needle.as_bytes();
                if needle.is_empty() || needle.len() > carry.len() {
                    continue;
                }
                for (start, window) in carry.windows(needle.len()).enumerate() {
                    if window == needle && start < split && start + needle.len() > split {
                        adjusted = adjusted.min(start);
                    }
                }
            }
            if adjusted == split {
                break;
            }
            split = adjusted;
        }
        if split == 0 {
            break;
        }
        let fragment: Vec<u8> = carry.drain(..split).collect();
        push_redacted_log_line(&fragment, markers, tail);
    }
    if eof && !carry.is_empty() {
        let trailing = std::mem::take(carry);
        push_redacted_log_line(&trailing, markers, tail);
    }
}

fn push_redacted_log_line(bytes: &[u8], markers: &[(String, String)], tail: &mut LogTail) {
    let mut end = bytes.len();
    if end > 0 && bytes[end - 1] == b'\n' {
        end -= 1;
    }
    if end > 0 && bytes[end - 1] == b'\r' {
        end -= 1;
    }
    let bytes = &bytes[..end];
    let mut text = String::from_utf8_lossy(bytes).into_owned();
    for (needle, replacement) in markers {
        if !needle.is_empty() {
            text = text.replace(needle, replacement);
        }
    }
    let line = sanitize_text(&text, 512);
    tail.bytes = tail.bytes.saturating_add(line.len());
    tail.lines.push(line);
    while tail.lines.len() > MAX_LOG_LINES || tail.bytes > MAX_LOG_BYTES {
        if let Some(first) = tail.lines.first() {
            tail.bytes = tail.bytes.saturating_sub(first.len());
        }
        if !tail.lines.is_empty() {
            tail.lines.remove(0);
        } else {
            break;
        }
    }
}

#[tauri::command]
pub async fn managed_runtime_status(
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<ManagedRuntimeStatus, BridgeError> {
    let runtime = Arc::clone(&runtime);
    let bridge = Arc::clone(&bridge);
    tauri::async_runtime::spawn_blocking(move || runtime.status(&bridge))
        .await
        .map_err(|_| {
            BridgeError::new(
                "runtime_unavailable",
                "managed runtime status worker failed",
            )
        })
}

#[tauri::command]
pub async fn managed_runtime_start(
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
    model_id: String,
) -> Result<ManagedRuntimeStartResponse, BridgeError> {
    if model_id.is_empty() || model_id.len() > 96 || model_id.chars().any(char::is_whitespace) {
        return Err(ManagedRuntimeError::new("invalid_payload", "invalid model id").into());
    }
    let runtime = Arc::clone(&runtime);
    let bridge = Arc::clone(&bridge);
    tauri::async_runtime::spawn_blocking(move || runtime.start(&model_id, &bridge))
        .await
        .map_err(|_| {
            BridgeError::new("runtime_unavailable", "managed runtime start worker failed")
        })?
}

#[tauri::command]
pub async fn managed_runtime_stop(
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<ManagedRuntimeStopResponse, BridgeError> {
    let runtime = Arc::clone(&runtime);
    let bridge = Arc::clone(&bridge);
    tauri::async_runtime::spawn_blocking(move || runtime.stop(&bridge))
        .await
        .map_err(|_| {
            BridgeError::new("runtime_unavailable", "managed runtime stop worker failed")
        })?
}

#[tauri::command]
pub fn managed_runtime_logs(state: State<'_, Arc<ManagedRuntimeSupervisor>>) -> ManagedRuntimeLogs {
    state.logs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capability_probe_output_preserves_flags_after_secret_like_substrings() {
        let output = format!("--cpu-mask-batch {}", REQUIRED_FLAGS.join(" "));

        let normalized = normalize_probe_output(format!("{output}\0"));

        assert!(!normalized.contains('\0'));
        for flag in REQUIRED_FLAGS {
            assert!(normalized.contains(flag), "missing required flag {flag}");
        }
    }

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
    fn runtime_args_keep_model_and_state_paths_inside_the_explicit_application_root() {
        let application_root = std::env::temp_dir()
            .join("localcomet-managed-runtime-override")
            .join("LocalComet");
        let model = application_root
            .join("models")
            .join("approved-model")
            .join("approved-model.gguf");
        let key = application_root.join("runtime-state").join("key-test.txt");
        let args = runtime_args(&model, 12345, &key, "approved-model");

        assert_eq!(args[1], model.into_os_string());
        assert_eq!(args[7], key.into_os_string());
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

    #[test]
    fn managed_attach_requires_exact_identity_and_inference_readiness() {
        let expected = ManagedRuntimeStartResponse {
            state: ManagedRuntimeState::Ready,
            model_state: ManagedModelState::Ready,
            inference_ready: true,
            provider_id: "managed-llama-cpp",
            model_id: "approved-model".into(),
            model_display_name: "Approved Model".into(),
            runtime_instance_id: "a".repeat(32),
            runtime_instance_fingerprint: "b".repeat(64),
        };
        let valid = json!({
            "provider_id": "managed-llama-cpp",
            "runtime_instance_id": expected.runtime_instance_id,
            "model_id": expected.model_id,
            "model_state": "Ready",
            "attached": true,
            "inference_ready": true,
        });
        assert!(validate_managed_attach_response(&valid, &expected).is_ok());
        let mut wrong_state = valid.clone();
        wrong_state["model_state"] = json!("Loading");
        assert!(validate_managed_attach_response(&wrong_state, &expected).is_err());
        let mut not_ready = valid.clone();
        not_ready["inference_ready"] = json!(false);
        assert!(validate_managed_attach_response(&not_ready, &expected).is_err());
        let mut wrong_model = valid;
        wrong_model["model_id"] = json!("other-model");
        assert!(validate_managed_attach_response(&wrong_model, &expected).is_err());

        let timeout = normalize_managed_attach_error(BridgeError::new(
            "first_token_timeout",
            "provider detail",
        ));
        assert_eq!(timeout.code, "model_load_timed_out");
        assert!(!timeout.message.contains("provider detail"));
        let failed =
            normalize_managed_attach_error(BridgeError::new("invalid_payload", "provider detail"));
        assert_eq!(failed.code, "model_load_failed");
    }

    #[test]
    fn model_load_deadline_returns_only_remaining_shared_budget() {
        let deadline = Instant::now() + Duration::from_millis(500);
        let remaining = remaining_model_load_timeout(deadline).unwrap();
        assert!(remaining > Duration::ZERO);
        assert!(remaining <= Duration::from_millis(500));
        assert!(remaining <= MODEL_LOAD_TIMEOUT);

        let expired = Instant::now() - Duration::from_millis(1);
        let error = remaining_model_load_timeout(expired).unwrap_err();
        assert_eq!(error.code, "model_load_timed_out");
    }

    #[test]
    fn startup_cancellation_is_immediate_and_generation_scoped() {
        let attempt = StartupAttempt {
            generation: 7,
            cancelled: Arc::new(AtomicBool::new(false)),
        };
        let mut inner = ManagedRuntimeInner {
            startup: Some(attempt.clone()),
            ..ManagedRuntimeInner::default()
        };
        assert!(startup_is_current(&inner, &attempt));
        assert!(attempt.ensure_active().is_ok());

        attempt.cancel();
        assert!(attempt.ensure_active().is_err());
        inner.startup = Some(StartupAttempt {
            generation: 8,
            cancelled: Arc::new(AtomicBool::new(false)),
        });
        assert!(!startup_is_current(&inner, &attempt));
    }

    #[test]
    fn log_redaction_survives_split_read_boundaries() {
        let markers = vec![("supersecret".into(), "<CREDENTIAL>".into())];
        let mut carry = Vec::new();
        let mut tail = LogTail::default();
        consume_log_bytes(&mut carry, b"prefix super", false, &markers, &mut tail);
        assert!(tail.lines.is_empty());
        consume_log_bytes(&mut carry, b"secret suffix\r\n", false, &markers, &mut tail);
        assert_eq!(tail.lines, vec!["prefix <CREDENTIAL> suffix"]);
        assert!(!tail.lines[0].contains("supersecret"));
    }

    #[test]
    fn runtime_and_model_states_serialize_separately() {
        let status = ManagedRuntimeStatus {
            engine: ENGINE_ID,
            state: ManagedRuntimeState::Starting,
            model_state: ManagedModelState::Loading,
            inference_ready: false,
            installation: "Installed".into(),
            runtime_version: None,
            runtime_instance_id: None,
            runtime_instance_fingerprint: None,
            model_id: Some("approved-model".into()),
            model_display_name: Some("Approved Model".into()),
            binding_fingerprint: None,
            last_error: None,
        };
        let value = serde_json::to_value(status).expect("serialize managed status");
        assert_eq!(value["state"], "Starting");
        assert_eq!(value["model_state"], "Loading");
        assert_eq!(value["inference_ready"], false);
    }

    #[test]
    fn bounded_reader_join_does_not_wait_past_finished_reader() {
        let reader = thread::spawn(|| {});
        join_reader_bounded(reader, Instant::now() + Duration::from_millis(100));
        assert!(SHUTDOWN_TIMEOUT <= Duration::from_secs(5));
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

    #[cfg(windows)]
    #[test]
    fn managed_http_slow_drip_cannot_extend_absolute_deadline() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("bind slow drip listener");
        let port = listener.local_addr().expect("listener address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept slow drip client");
            let mut request = [0_u8; 1024];
            let _ = stream.read(&mut request);
            for byte in b"HTTP/1.1 200 OK\r\n" {
                if stream.write_all(&[*byte]).is_err() {
                    break;
                }
                thread::sleep(Duration::from_millis(20));
            }
        });
        let started = Instant::now();
        let result = http_get_json(
            port,
            "/health",
            &"a".repeat(64),
            std::process::id(),
            Instant::now() + Duration::from_millis(80),
        );
        assert!(result.is_err());
        assert!(started.elapsed() < Duration::from_millis(500));
        server.join().expect("join slow drip server");
    }
}
