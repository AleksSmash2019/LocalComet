use crate::ipc;
use crate::windows_job::{ContainedSidecarProcess, SidecarLaunchSpec};
use std::collections::{HashMap, VecDeque};
use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub const PYTHON_ISOLATED_ARG: &str = "-I";
pub const PYTHON_NO_BYTECODE_ARG: &str = "-B";
#[cfg(debug_assertions)]
pub const PYTHON_SIDECAR_RUNNER: &str = "tools/run_localcomet_desktop_sidecar.py";
#[cfg(not(debug_assertions))]
pub const RELEASE_SIDECAR_EXE: &str = "localcomet-core.exe";
#[cfg(not(debug_assertions))]
pub const RELEASE_SIDECAR_RUNNER: &str = "app/tools/run_localcomet_desktop_sidecar.py";
#[allow(dead_code)]
pub const HEALTH_METHOD: &str = "app.health";
pub const SHUTDOWN_METHOD: &str = "app.shutdown";
const IPC_WRITE_TIMEOUT: Duration = Duration::from_secs(2);

pub trait SidecarFrameRouter: Send + Sync {
    fn route_frame(&self, frame: Vec<u8>);
    fn fail_pending(&self, code: &str, message: &str);
}

#[derive(Debug)]
pub enum SupervisorError {
    Unavailable(String),
    Io(io::Error),
    ReadinessTimeout,
    ExitedBeforeReady,
}

impl std::fmt::Display for SupervisorError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unavailable(message) => write!(formatter, "sidecar unavailable: {message}"),
            Self::Io(error) => write!(formatter, "sidecar I/O error: {error}"),
            Self::ReadinessTimeout => write!(formatter, "sidecar readiness timed out"),
            Self::ExitedBeforeReady => write!(formatter, "sidecar exited before readiness"),
        }
    }
}

impl std::error::Error for SupervisorError {}

impl From<io::Error> for SupervisorError {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}

#[derive(Clone, Debug)]
pub enum SidecarProgram {
    #[cfg(debug_assertions)]
    DebugPython {
        python_exe: PathBuf,
        project_root: PathBuf,
        runner: PathBuf,
    },
    #[cfg(not(debug_assertions))]
    ReleaseBundle {
        executable: PathBuf,
        current_dir: PathBuf,
        runner: PathBuf,
    },
    #[cfg(debug_assertions)]
    Unavailable { reason: String },
}

#[derive(Clone, Debug)]
pub struct SupervisorConfig {
    pub program: SidecarProgram,
    pub env: Vec<(OsString, OsString)>,
}

impl SupervisorConfig {
    pub fn discover() -> Self {
        #[cfg(debug_assertions)]
        {
            Self::debug_from_environment()
        }
        #[cfg(not(debug_assertions))]
        {
            Self::release_from_current_exe()
        }
    }

    #[cfg(debug_assertions)]
    pub fn debug_for_tests(project_root: PathBuf, python_exe: PathBuf) -> Self {
        let runner = project_root.join(PYTHON_SIDECAR_RUNNER);
        let env = minimal_sidecar_environment(Some(&python_exe));
        Self {
            program: SidecarProgram::DebugPython {
                python_exe,
                project_root,
                runner,
            },
            env,
        }
    }

    pub fn to_launch_spec(&self) -> Result<SidecarLaunchSpec, SupervisorError> {
        match &self.program {
            #[cfg(debug_assertions)]
            SidecarProgram::DebugPython {
                python_exe,
                project_root,
                runner,
            } => {
                if !python_exe.is_file() {
                    return Err(SupervisorError::Unavailable(
                        "debug Python executable missing".into(),
                    ));
                }
                if !runner.is_file()
                    || runner
                        .symlink_metadata()
                        .map(|meta| meta.file_type().is_symlink())
                        .unwrap_or(true)
                {
                    return Err(SupervisorError::Unavailable(
                        "debug sidecar runner missing or symlinked".into(),
                    ));
                }
                Ok(SidecarLaunchSpec {
                    executable: python_exe.clone(),
                    args: vec![
                        OsString::from(PYTHON_ISOLATED_ARG),
                        OsString::from(PYTHON_NO_BYTECODE_ARG),
                        runner.as_os_str().to_os_string(),
                    ],
                    current_dir: project_root.clone(),
                    env: self.env.clone(),
                })
            }
            #[cfg(not(debug_assertions))]
            SidecarProgram::ReleaseBundle {
                executable,
                current_dir,
                runner,
            } => {
                if !executable.is_file() {
                    return Err(SupervisorError::Unavailable(
                        "release sidecar executable missing".into(),
                    ));
                }
                if !runner.is_file()
                    || runner
                        .symlink_metadata()
                        .map(|meta| meta.file_type().is_symlink())
                        .unwrap_or(true)
                {
                    return Err(SupervisorError::Unavailable(
                        "release sidecar runner missing or symlinked".into(),
                    ));
                }
                Ok(SidecarLaunchSpec {
                    executable: executable.clone(),
                    args: vec![
                        OsString::from(PYTHON_ISOLATED_ARG),
                        OsString::from(PYTHON_NO_BYTECODE_ARG),
                        runner.as_os_str().to_os_string(),
                    ],
                    current_dir: current_dir.clone(),
                    env: self.env.clone(),
                })
            }
            #[cfg(debug_assertions)]
            SidecarProgram::Unavailable { reason } => {
                Err(SupervisorError::Unavailable(reason.clone()))
            }
        }
    }

    #[cfg(debug_assertions)]
    fn debug_from_environment() -> Self {
        let root = std::env::var_os("LOCALCOMET_TEST_PROJECT_ROOT")
            .map(PathBuf::from)
            .or_else(locate_project_root);
        let python = std::env::var_os("LOCALCOMET_TEST_PYTHON")
            .map(PathBuf::from)
            .or_else(find_python_on_path);

        match (root, python) {
            (Some(project_root), Some(python_exe)) => {
                Self::debug_for_tests(project_root, python_exe)
            }
            _ => Self {
                program: SidecarProgram::Unavailable {
                    reason: "debug sidecar root or Python executable not found".into(),
                },
                env: minimal_sidecar_environment(None),
            },
        }
    }

    #[cfg(not(debug_assertions))]
    pub fn release_from_current_exe() -> Self {
        let current_dir = std::env::current_exe()
            .ok()
            .and_then(|path| path.parent().map(Path::to_path_buf))
            .unwrap_or_else(|| PathBuf::from("."));
        let executable = current_dir.join(RELEASE_SIDECAR_EXE);
        let runner = current_dir.join(RELEASE_SIDECAR_RUNNER);
        let env = minimal_sidecar_environment(Some(&executable));
        Self {
            program: SidecarProgram::ReleaseBundle {
                executable,
                current_dir,
                runner,
            },
            env,
        }
    }
}

#[derive(Default)]
struct SupervisorState {
    process: Option<ContainedSidecarProcess>,
    next_request: u64,
    shutting_down: bool,
}

#[derive(Default)]
struct SupervisorShared {
    saw_python_hello: AtomicBool,
    saw_health_ok: AtomicBool,
    saw_goodbye: AtomicBool,
    last_frame: Mutex<Option<String>>,
    stderr_tail: Mutex<String>,
    router: Mutex<Option<Arc<dyn SidecarFrameRouter>>>,
    readiness: Mutex<SidecarReadinessInner>,
    generation_counter: AtomicU64,
}

#[derive(Default)]
struct SidecarReadinessInner {
    state: SidecarReadinessState,
    generation: Option<SidecarGeneration>,
    health_registry: PendingHealthRegistry,
    last_successful_health_unix_ms: Option<u64>,
    last_failure_code: Option<String>,
}

#[derive(Clone, Debug)]
pub struct SupervisorSnapshot {
    pub running: bool,
    pub saw_python_hello: bool,
    pub saw_health_ok: bool,
    pub saw_goodbye: bool,
    pub last_frame: Option<String>,
    pub stderr_tail: String,
}

#[allow(dead_code)]
pub const MAX_PENDING_HEALTH_REQUESTS: usize = 8;
#[allow(dead_code)]
pub const MAX_COMPLETED_HEALTH_TOMBSTONES: usize = 32;
#[allow(dead_code)]
pub const PENDING_HEALTH_TTL: Duration = Duration::from_secs(10);
#[allow(dead_code)]
pub const COMPLETED_TOMBSTONE_TTL: Duration = Duration::from_secs(60);
#[allow(dead_code)]
pub const MAX_HEALTH_JSON_DEPTH: usize = 16;

#[allow(dead_code)]
pub const HEALTH_ERR_NOT_RUNNING: &str = "sidecar_not_running";
#[allow(dead_code)]
pub const HEALTH_ERR_START_TIMEOUT: &str = "sidecar_start_timeout";
#[allow(dead_code)]
pub const HEALTH_ERR_HEALTH_TIMEOUT: &str = "sidecar_health_timeout";
#[allow(dead_code)]
pub const HEALTH_ERR_FRAME_INVALID: &str = "sidecar_health_frame_invalid";
#[allow(dead_code)]
pub const HEALTH_ERR_PROTOCOL_MISMATCH: &str = "sidecar_health_protocol_mismatch";
#[allow(dead_code)]
pub const HEALTH_ERR_REQUEST_UNKNOWN: &str = "sidecar_health_request_unknown";
#[allow(dead_code)]
pub const HEALTH_ERR_RESPONSE_DUPLICATE: &str = "sidecar_health_response_duplicate";
#[allow(dead_code)]
pub const HEALTH_ERR_GENERATION_MISMATCH: &str = "sidecar_health_generation_mismatch";
#[allow(dead_code)]
pub const HEALTH_ERR_NONCE_MISMATCH: &str = "sidecar_health_nonce_mismatch";
#[allow(dead_code)]
pub const HEALTH_ERR_RUNTIME_MISMATCH: &str = "sidecar_health_runtime_mismatch";
#[allow(dead_code)]
pub const HEALTH_ERR_CAPABILITY_MISMATCH: &str = "sidecar_health_capability_mismatch";
#[allow(dead_code)]
pub const HEALTH_ERR_STATUS_INVALID: &str = "sidecar_health_status_invalid";
#[allow(dead_code)]
pub const HEALTH_ERR_PROCESS_EXITED: &str = "sidecar_process_exited";
#[allow(dead_code)]
pub const HEALTH_ERR_STOPPING: &str = "sidecar_stopping";
pub const HEALTH_ERR_GENERATION_EXHAUSTED: &str = "sidecar_generation_exhausted";
const HEALTH_ERR_PROBE_SEND_FAILED: &str = "sidecar_health_probe_send_failed";
const HEALTH_ERR_CSPRNG_FAILED: &str = "sidecar_csprng_failed";

fn readiness_failure_code(error: &SupervisorError) -> &'static str {
    match error {
        SupervisorError::Unavailable(code) => match code.as_str() {
            HEALTH_ERR_NOT_RUNNING => HEALTH_ERR_NOT_RUNNING,
            HEALTH_ERR_HEALTH_TIMEOUT => HEALTH_ERR_HEALTH_TIMEOUT,
            HEALTH_ERR_FRAME_INVALID => HEALTH_ERR_FRAME_INVALID,
            _ => HEALTH_ERR_PROBE_SEND_FAILED,
        },
        SupervisorError::Io(_) => "sidecar_write_failed",
        SupervisorError::ReadinessTimeout => HEALTH_ERR_START_TIMEOUT,
        SupervisorError::ExitedBeforeReady => HEALTH_ERR_PROCESS_EXITED,
    }
}

#[allow(dead_code)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum SidecarReadinessState {
    #[default]
    Stopped,
    Starting,
    ChallengeSent,
    Ready,
    Degraded,
    Stopping,
    StartFailed,
}

#[derive(Clone, Debug)]
pub struct SidecarGeneration {
    pub generation_id: u64,
    pub startup_nonce: String,
    pub runtime_instance_id: String,
}

#[allow(dead_code)]
#[derive(Clone, Debug)]
pub struct SidecarHealthSnapshot {
    pub state: SidecarReadinessState,
    pub generation_id: u64,
    pub runtime_instance_id: Option<String>,
    pub last_successful_health_unix_ms: Option<u64>,
    pub last_failure_code: Option<String>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HealthCompletion {
    Pending,
    Completed,
}

#[allow(dead_code)]
struct PendingHealthEntry {
    generation_id: u64,
    created_at: Instant,
    deadline_unix_ms: u64,
    state: HealthCompletion,
}

#[allow(dead_code)]
#[derive(Default)]
pub struct PendingHealthRegistry {
    pending: HashMap<String, PendingHealthEntry>,
    tombstones: VecDeque<(String, Instant)>,
}

#[allow(dead_code)]
impl PendingHealthRegistry {
    pub fn insert(
        &mut self,
        request_id: String,
        generation_id: u64,
        deadline_unix_ms: u64,
    ) -> Result<(), &'static str> {
        self.evict_expired();
        if self.pending.len() >= MAX_PENDING_HEALTH_REQUESTS {
            return Err(HEALTH_ERR_FRAME_INVALID);
        }
        if self.pending.contains_key(&request_id) || self.is_known_tombstone(&request_id) {
            return Err(HEALTH_ERR_RESPONSE_DUPLICATE);
        }
        self.pending.insert(
            request_id,
            PendingHealthEntry {
                generation_id,
                created_at: Instant::now(),
                deadline_unix_ms,
                state: HealthCompletion::Pending,
            },
        );
        Ok(())
    }

    pub fn complete(
        &mut self,
        request_id: &str,
        expected_generation_id: u64,
        received_at_unix_ms: u64,
    ) -> Result<HealthCompletion, &'static str> {
        self.evict_expired();
        if self.is_known_tombstone(request_id) {
            return Err(HEALTH_ERR_RESPONSE_DUPLICATE);
        }
        let entry = self
            .pending
            .get_mut(request_id)
            .ok_or(HEALTH_ERR_REQUEST_UNKNOWN)?;
        if entry.generation_id != expected_generation_id {
            return Err(HEALTH_ERR_GENERATION_MISMATCH);
        }
        if received_at_unix_ms > entry.deadline_unix_ms {
            return Err(HEALTH_ERR_HEALTH_TIMEOUT);
        }
        if entry.state == HealthCompletion::Completed {
            return Err(HEALTH_ERR_RESPONSE_DUPLICATE);
        }
        entry.state = HealthCompletion::Completed;
        let now = Instant::now();
        self.tombstones.push_back((request_id.to_owned(), now));
        while self.tombstones.len() > MAX_COMPLETED_HEALTH_TOMBSTONES {
            self.tombstones.pop_front();
        }
        Ok(HealthCompletion::Completed)
    }

    pub fn is_known_tombstone(&self, request_id: &str) -> bool {
        self.tombstones.iter().any(|(id, _)| id == request_id)
    }

    pub fn cancel_generation(&mut self, generation_id: u64) {
        self.pending
            .retain(|_, entry| entry.generation_id != generation_id);
    }

    fn evict_expired(&mut self) {
        let now = Instant::now();
        self.pending
            .retain(|_, entry| now.duration_since(entry.created_at) < PENDING_HEALTH_TTL);
        self.tombstones
            .retain(|(_, created)| now.duration_since(*created) < COMPLETED_TOMBSTONE_TTL);
    }
}

pub fn generate_startup_nonce() -> Result<String, &'static str> {
    let mut bytes = [0u8; 32];
    getrandom_fill(&mut bytes)?;
    Ok(format!("scn_{}", hex_encode(&bytes)))
}

pub fn generate_runtime_instance_id() -> Result<String, &'static str> {
    let mut bytes = [0u8; 16];
    getrandom_fill(&mut bytes)?;
    Ok(format!("rti_{}", hex_encode(&bytes)))
}

#[allow(dead_code)]
pub fn generate_health_request_id() -> Result<String, &'static str> {
    let mut bytes = [0u8; 16];
    getrandom_fill(&mut bytes)?;
    Ok(format!("hreq_{}", hex_encode(&bytes)))
}

fn getrandom_fill(bytes: &mut [u8]) -> Result<(), &'static str> {
    #[cfg(target_os = "windows")]
    {
        use windows_sys::Win32::Security::Cryptography::{
            BCryptGenRandom, BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        };
        // NTSTATUS success values have the high bit clear; on failure we must
        // not continue with silently zeroed nonces.
        let status = unsafe {
            BCryptGenRandom(
                std::ptr::null_mut(),
                bytes.as_mut_ptr(),
                bytes.len() as u32,
                BCRYPT_USE_SYSTEM_PREFERRED_RNG,
            )
        };
        if status < 0 {
            return Err(HEALTH_ERR_CSPRNG_FAILED);
        }
        Ok(())
    }
    #[cfg(not(target_os = "windows"))]
    {
        use std::io::Read;
        let mut f = std::fs::File::open("/dev/urandom").map_err(|_| HEALTH_ERR_CSPRNG_FAILED)?;
        f.read_exact(bytes).map_err(|_| HEALTH_ERR_CSPRNG_FAILED)?;
        Ok(())
    }
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn validate_health_response(
    payload: &serde_json::Value,
    expected_generation_id: u64,
    expected_nonce: &str,
    expected_runtime_instance_id: &str,
) -> Result<u64, &'static str> {
    let protocol_version = payload
        .get("protocolVersion")
        .and_then(serde_json::Value::as_u64);
    if protocol_version != Some(1) {
        return Err(HEALTH_ERR_PROTOCOL_MISMATCH);
    }
    let status = payload
        .get("status")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    if !matches!(status, "starting" | "ready" | "degraded" | "stopping") {
        return Err(HEALTH_ERR_STATUS_INVALID);
    }
    let caps = payload.get("capabilities");
    let tool_execution = caps
        .and_then(|c| c.get("toolExecution"))
        .and_then(serde_json::Value::as_bool);
    if tool_execution != Some(false) {
        return Err(HEALTH_ERR_CAPABILITY_MISMATCH);
    }
    let generation_id = payload
        .get("generationId")
        .and_then(serde_json::Value::as_u64);
    if generation_id != Some(expected_generation_id) {
        return Err(HEALTH_ERR_GENERATION_MISMATCH);
    }
    let nonce = payload
        .get("startupNonce")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    if nonce != expected_nonce {
        return Err(HEALTH_ERR_NONCE_MISMATCH);
    }
    let rti = payload
        .get("runtimeInstanceId")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    if rti != expected_runtime_instance_id {
        return Err(HEALTH_ERR_RUNTIME_MISMATCH);
    }
    let received_at = payload
        .get("receivedAtUnixMs")
        .and_then(serde_json::Value::as_u64)
        .ok_or(HEALTH_ERR_FRAME_INVALID)?;
    Ok(received_at)
}

fn unix_time_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

fn generation_is_active(shared: &SupervisorShared, generation_id: u64) -> bool {
    shared
        .readiness
        .lock()
        .expect("readiness lock poisoned")
        .generation
        .as_ref()
        .is_some_and(|generation| generation.generation_id == generation_id)
}

fn clear_readiness_on_exit(shared: &SupervisorShared, generation_id: u64) -> bool {
    let mut readiness = shared.readiness.lock().expect("readiness lock poisoned");
    if readiness
        .generation
        .as_ref()
        .map(|generation| generation.generation_id)
        != Some(generation_id)
    {
        return false;
    }
    shared.saw_python_hello.store(false, Ordering::SeqCst);
    shared.saw_health_ok.store(false, Ordering::SeqCst);
    shared.saw_goodbye.store(false, Ordering::SeqCst);
    readiness.state = SidecarReadinessState::Stopped;
    readiness.last_failure_code = Some(HEALTH_ERR_PROCESS_EXITED.to_owned());
    readiness.health_registry.cancel_generation(generation_id);
    readiness.generation = None;
    true
}

pub struct DesktopSidecarSupervisor {
    config: SupervisorConfig,
    transition: Mutex<()>,
    state: Mutex<SupervisorState>,
    shared: Arc<SupervisorShared>,
}

impl DesktopSidecarSupervisor {
    pub fn new(config: SupervisorConfig) -> Self {
        Self {
            config,
            transition: Mutex::new(()),
            state: Mutex::new(SupervisorState::default()),
            shared: Arc::new(SupervisorShared::default()),
        }
    }

    #[allow(dead_code)]
    pub fn start(&self) -> Result<(), SupervisorError> {
        let _transition = self.transition.lock().expect("transition lock poisoned");
        self.start_under_transition()
    }

    fn start_under_transition(&self) -> Result<(), SupervisorError> {
        let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
        if state.process.is_some() {
            return Ok(());
        }

        let spec = self.config.to_launch_spec()?;
        state.next_request = 0;
        state.shutting_down = false;
        self.shared.saw_python_hello.store(false, Ordering::SeqCst);
        self.shared.saw_health_ok.store(false, Ordering::SeqCst);
        self.shared.saw_goodbye.store(false, Ordering::SeqCst);
        *self
            .shared
            .last_frame
            .lock()
            .expect("sidecar frame lock poisoned") = None;
        self.shared
            .stderr_tail
            .lock()
            .expect("sidecar stderr lock poisoned")
            .clear();
        // MVP-P0-C-R1: fail-closed generation allocation. On overflow we do not
        // launch a sidecar and we do not reuse generation 1.
        let previous = self.shared.generation_counter.load(Ordering::SeqCst);
        let generation_id = match previous.checked_add(1) {
            Some(next) => next,
            None => {
                let mut readiness = self
                    .shared
                    .readiness
                    .lock()
                    .expect("readiness lock poisoned");
                readiness.state = SidecarReadinessState::StartFailed;
                readiness.generation = None;
                readiness.last_failure_code = Some(HEALTH_ERR_GENERATION_EXHAUSTED.to_owned());
                self.shared.saw_health_ok.store(false, Ordering::SeqCst);
                return Err(SupervisorError::Unavailable(
                    HEALTH_ERR_GENERATION_EXHAUSTED.to_owned(),
                ));
            }
        };
        self.shared
            .generation_counter
            .store(generation_id, Ordering::SeqCst);
        let generation = match (generate_startup_nonce(), generate_runtime_instance_id()) {
            (Ok(startup_nonce), Ok(runtime_instance_id)) => SidecarGeneration {
                generation_id,
                startup_nonce,
                runtime_instance_id,
            },
            _ => {
                drop(state);
                self.rollback_start_under_transition(generation_id, None, HEALTH_ERR_CSPRNG_FAILED);
                return Err(SupervisorError::Unavailable(
                    HEALTH_ERR_CSPRNG_FAILED.to_owned(),
                ));
            }
        };
        {
            let mut readiness = self
                .shared
                .readiness
                .lock()
                .expect("readiness lock poisoned");
            readiness.state = SidecarReadinessState::Starting;
            readiness.generation = Some(generation);
            readiness.health_registry = PendingHealthRegistry::default();
            readiness.last_failure_code = None;
        }
        let mut process = match ContainedSidecarProcess::spawn(&spec) {
            Ok(process) => process,
            Err(error) => {
                drop(state);
                self.rollback_start_under_transition(generation_id, None, "sidecar_spawn_failed");
                return Err(SupervisorError::Io(error));
            }
        };
        let hello = match ipc::desktop_hello_frame("desk-hello-000001", "localcomet-desktop") {
            Ok(hello) => hello,
            Err(error) => {
                drop(state);
                self.rollback_start_under_transition(
                    generation_id,
                    Some(process),
                    "sidecar_hello_failed",
                );
                return Err(error.into());
            }
        };
        if let Err(error) = process.write_frame_bounded(&hello, IPC_WRITE_TIMEOUT) {
            drop(state);
            self.rollback_start_under_transition(
                generation_id,
                Some(process),
                "sidecar_hello_write_failed",
            );
            return Err(SupervisorError::Io(error));
        }
        if let Some(stdout) = process.take_stdout() {
            spawn_stdout_reader(stdout, Arc::clone(&self.shared), generation_id);
        }
        if let Some(stderr) = process.take_stderr() {
            spawn_stderr_reader(stderr, Arc::clone(&self.shared));
        }
        state.process = Some(process);
        {
            let mut readiness = self
                .shared
                .readiness
                .lock()
                .expect("readiness lock poisoned");
            readiness.state = SidecarReadinessState::ChallengeSent;
        }
        Ok(())
    }

    pub fn start_and_wait_ready(&self, timeout: Duration) -> Result<(), SupervisorError> {
        let _transition = self.transition.lock().expect("transition lock poisoned");
        self.start_under_transition()?;
        if let Err(error) = self.send_health_probe() {
            self.abort_start_under_transition(readiness_failure_code(&error));
            return Err(error);
        }

        let deadline = Instant::now() + timeout;
        loop {
            let snapshot = self.snapshot();
            if snapshot.running && snapshot.saw_python_hello && snapshot.saw_health_ok {
                return Ok(());
            }
            if !snapshot.running {
                self.abort_start_under_transition(HEALTH_ERR_PROCESS_EXITED);
                return Err(SupervisorError::ExitedBeforeReady);
            }
            if Instant::now() >= deadline {
                self.abort_start_under_transition(HEALTH_ERR_START_TIMEOUT);
                return Err(SupervisorError::ReadinessTimeout);
            }
            thread::sleep(Duration::from_millis(20));
        }
    }

    pub fn set_frame_router(&self, router: Arc<dyn SidecarFrameRouter>) {
        *self
            .shared
            .router
            .lock()
            .expect("sidecar router lock poisoned") = Some(router);
    }

    pub fn send_ipc_frame(&self, frame: Vec<u8>) -> Result<(), SupervisorError> {
        let (result, failed_process, generation_id) = {
            let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
            if state.shutting_down {
                return Err(SupervisorError::Unavailable("sidecar is stopping".into()));
            }
            let result = state
                .process
                .as_mut()
                .ok_or_else(|| {
                    SupervisorError::Unavailable("sidecar process is not running".into())
                })
                .and_then(|process| {
                    process
                        .write_frame_bounded(&frame, IPC_WRITE_TIMEOUT)
                        .map_err(SupervisorError::Io)
                });
            let generation_id = self
                .shared
                .readiness
                .lock()
                .expect("readiness lock poisoned")
                .generation
                .as_ref()
                .map(|generation| generation.generation_id);
            let failed_process = result.as_ref().err().and_then(|_| state.process.take());
            (result, failed_process, generation_id)
        };
        if let Some(process) = failed_process {
            process.terminate(1);
            let _ = process.wait_bounded(1_000);
            if let Some(generation_id) = generation_id {
                if self.invalidate_generation(
                    generation_id,
                    SidecarReadinessState::StartFailed,
                    "sidecar_write_failed",
                ) {
                    self.fail_pending("sidecar_write_failed", "sidecar pipe write failed");
                }
            }
        }
        result
    }

    pub fn send_health_probe(&self) -> Result<(), SupervisorError> {
        let sequence = {
            let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
            let sequence = state.next_request;
            state.next_request += 1;
            sequence
        };
        // MVP-P0-C-R1: cryptographic hreq_ id, registered in the bounded pending
        // registry before the frame is written. No prefix/sequential correlation.
        let request_id = generate_health_request_id()
            .map_err(|code| SupervisorError::Unavailable(code.to_owned()))?;
        let sent_at_unix_ms = unix_time_ms();
        let deadline_unix_ms = sent_at_unix_ms
            .checked_add(PENDING_HEALTH_TTL.as_millis() as u64)
            .ok_or_else(|| SupervisorError::Unavailable(HEALTH_ERR_HEALTH_TIMEOUT.to_owned()))?;
        let (generation_id, startup_nonce, runtime_instance_id) = {
            let mut readiness = self
                .shared
                .readiness
                .lock()
                .expect("readiness lock poisoned");
            let generation = readiness
                .generation
                .clone()
                .ok_or_else(|| SupervisorError::Unavailable(HEALTH_ERR_NOT_RUNNING.to_owned()))?;
            readiness
                .health_registry
                .insert(
                    request_id.clone(),
                    generation.generation_id,
                    deadline_unix_ms,
                )
                .map_err(|code| SupervisorError::Unavailable(code.to_owned()))?;
            (
                generation.generation_id,
                generation.startup_nonce,
                generation.runtime_instance_id,
            )
        };
        self.send_ipc_frame(ipc::health_check_request_frame(
            &request_id,
            generation_id,
            &startup_nonce,
            &runtime_instance_id,
            sent_at_unix_ms as i64,
            sequence,
        )?)
    }

    pub fn snapshot(&self) -> SupervisorSnapshot {
        let running = self
            .state
            .lock()
            .expect("sidecar supervisor lock poisoned")
            .process
            .as_ref()
            .map(ContainedSidecarProcess::is_running)
            .unwrap_or(false);
        SupervisorSnapshot {
            running,
            saw_python_hello: self.shared.saw_python_hello.load(Ordering::SeqCst),
            saw_health_ok: self.shared.saw_health_ok.load(Ordering::SeqCst),
            saw_goodbye: self.shared.saw_goodbye.load(Ordering::SeqCst),
            last_frame: self
                .shared
                .last_frame
                .lock()
                .expect("sidecar frame lock poisoned")
                .clone(),
            stderr_tail: self
                .shared
                .stderr_tail
                .lock()
                .expect("sidecar stderr lock poisoned")
                .clone(),
        }
    }

    pub fn shutdown(&self) -> Result<(), SupervisorError> {
        let _transition = self.transition.lock().expect("transition lock poisoned");
        self.shutdown_under_transition()
    }

    fn shutdown_under_transition(&self) -> Result<(), SupervisorError> {
        self.invalidate_current_generation(SidecarReadinessState::Stopping, HEALTH_ERR_STOPPING);
        let (mut process, sequence) = {
            let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
            if state.shutting_down {
                return Ok(());
            }
            state.shutting_down = true;
            let sequence = state.next_request;
            state.next_request += 1;
            (state.process.take(), sequence)
        };

        let send_result = if let Some(process) = process.as_mut() {
            let frame = ipc::lifecycle_request_frame(
                &format!("desk-shutdown-{sequence:06}"),
                SHUTDOWN_METHOD,
                sequence,
            )?;
            process
                .write_frame_bounded(&frame, IPC_WRITE_TIMEOUT)
                .map_err(SupervisorError::Io)
        } else {
            Ok(())
        };

        if let Some(process) = process.as_ref() {
            if send_result.is_err() {
                process.terminate(1);
                let _ = process.wait_bounded(1_000);
            } else if !process.wait_bounded(1_500) {
                process.terminate(0);
                let _ = process.wait_bounded(1_000);
            }
        }
        drop(process);
        self.state
            .lock()
            .expect("sidecar supervisor lock poisoned")
            .shutting_down = false;
        self.fail_pending("sidecar_shutdown", "sidecar shutdown");
        send_result
    }

    fn invalidate_generation(
        &self,
        generation_id: u64,
        state: SidecarReadinessState,
        code: &str,
    ) -> bool {
        let mut readiness = self
            .shared
            .readiness
            .lock()
            .expect("readiness lock poisoned");
        if readiness
            .generation
            .as_ref()
            .map(|generation| generation.generation_id)
            != Some(generation_id)
        {
            return false;
        }
        self.shared.saw_python_hello.store(false, Ordering::SeqCst);
        self.shared.saw_health_ok.store(false, Ordering::SeqCst);
        self.shared.saw_goodbye.store(false, Ordering::SeqCst);
        readiness.state = state;
        readiness.last_failure_code = Some(code.to_owned());
        readiness.health_registry.cancel_generation(generation_id);
        readiness.generation = None;
        true
    }

    fn invalidate_current_generation(&self, state: SidecarReadinessState, code: &str) {
        let generation_id = self
            .shared
            .readiness
            .lock()
            .expect("readiness lock poisoned")
            .generation
            .as_ref()
            .map(|generation| generation.generation_id);
        if let Some(generation_id) = generation_id {
            self.invalidate_generation(generation_id, state, code);
        }
    }

    fn rollback_start_under_transition(
        &self,
        generation_id: u64,
        process: Option<ContainedSidecarProcess>,
        code: &str,
    ) {
        if let Some(process) = process {
            process.terminate(1);
            let _ = process.wait_bounded(1_000);
        }
        self.invalidate_generation(generation_id, SidecarReadinessState::StartFailed, code);
    }

    fn abort_start_under_transition(&self, code: &str) {
        let generation_id = self
            .shared
            .readiness
            .lock()
            .expect("readiness lock poisoned")
            .generation
            .as_ref()
            .map(|generation| generation.generation_id);
        let process = self
            .state
            .lock()
            .expect("sidecar supervisor lock poisoned")
            .process
            .take();
        if let Some(process) = process {
            process.terminate(1);
            let _ = process.wait_bounded(1_000);
        }
        if let Some(generation_id) = generation_id {
            self.invalidate_generation(generation_id, SidecarReadinessState::StartFailed, code);
        }
    }

    fn fail_pending(&self, code: &str, message: &str) {
        let router = self
            .shared
            .router
            .lock()
            .expect("sidecar router lock poisoned")
            .clone();
        if let Some(router) = router {
            router.fail_pending(code, message);
        }
    }
}

impl Default for DesktopSidecarSupervisor {
    fn default() -> Self {
        Self::new(SupervisorConfig::discover())
    }
}

impl Drop for DesktopSidecarSupervisor {
    fn drop(&mut self) {
        let _ = self.shutdown();
    }
}

fn spawn_stdout_reader(mut stdout: File, shared: Arc<SupervisorShared>, generation_id: u64) {
    let _ = thread::Builder::new()
        .name("localcomet-sidecar-stdout".into())
        .spawn(move || {
            while let Ok(frame) = ipc::read_frame(&mut stdout) {
                if !generation_is_active(&shared, generation_id) {
                    continue;
                }
                let text = String::from_utf8_lossy(&frame).into_owned();
                observe_lifecycle_frame(&frame, &shared, generation_id);
                if !generation_is_active(&shared, generation_id) {
                    continue;
                }
                *shared
                    .last_frame
                    .lock()
                    .expect("sidecar frame lock poisoned") = Some(limit_text(&text, 4096));
                let router = shared
                    .router
                    .lock()
                    .expect("sidecar router lock poisoned")
                    .clone();
                if let Some(router) = router {
                    router.route_frame(frame);
                }
            }
            if clear_readiness_on_exit(&shared, generation_id) {
                let router = shared
                    .router
                    .lock()
                    .expect("sidecar router lock poisoned")
                    .clone();
                if let Some(router) = router {
                    router.fail_pending("sidecar_unavailable", "sidecar stdout closed");
                }
            }
        });
}

fn observe_lifecycle_frame(frame: &[u8], shared: &SupervisorShared, generation_id: u64) {
    if !generation_is_active(shared, generation_id) {
        return;
    }
    // MVP-P0-C-R1: every inbound frame goes through the hardened semantic
    // parser (decoded duplicate keys, depth, non-finite, trailing data).
    let Ok(message) = ipc::parse_health_frame(frame) else {
        return;
    };
    let message_type = message.get("type").and_then(serde_json::Value::as_str);
    if message_type == Some("hello")
        && message
            .pointer("/payload/role")
            .and_then(serde_json::Value::as_str)
            == Some("python_core")
    {
        shared.saw_python_hello.store(true, Ordering::SeqCst);
    }
    if message_type == Some("response") {
        let outer_id = message
            .get("id")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        let reply_to = message
            .get("reply_to")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        let payload = message.get("payload");
        // Only typed health.status payloads participate in readiness.
        let is_health_status = payload
            .and_then(|p| p.get("type"))
            .and_then(serde_json::Value::as_str)
            == Some("health.status");
        if is_health_status {
            if let Some(payload) = payload {
                let mut readiness = shared.readiness.lock().expect("readiness lock poisoned");
                let inner_request_id = payload
                    .get("requestId")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                let generation = readiness.generation.clone();
                let mut failure: Option<&'static str> = None;

                if inner_request_id.is_empty()
                    || outer_id != inner_request_id
                    || reply_to != inner_request_id
                {
                    failure = Some(HEALTH_ERR_FRAME_INVALID);
                } else if let Some(gen) = generation {
                    match validate_health_response(
                        payload,
                        gen.generation_id,
                        &gen.startup_nonce,
                        &gen.runtime_instance_id,
                    ) {
                        Err(code) => failure = Some(code),
                        Ok(received_at_unix_ms) => {
                            if payload.get("status").and_then(serde_json::Value::as_str)
                                != Some("ready")
                            {
                                failure = Some(HEALTH_ERR_STATUS_INVALID);
                            } else {
                                // Authoritative pending-registry correlation, then
                                // atomic one-time completion, then READY.
                                match readiness.health_registry.complete(
                                    inner_request_id,
                                    gen.generation_id,
                                    received_at_unix_ms,
                                ) {
                                    Ok(_) => {
                                        shared.saw_health_ok.store(true, Ordering::SeqCst);
                                        readiness.state = SidecarReadinessState::Ready;
                                        readiness.last_successful_health_unix_ms =
                                            Some(received_at_unix_ms);
                                        readiness.last_failure_code = None;
                                    }
                                    Err(code) => failure = Some(code),
                                }
                            }
                        }
                    }
                } else {
                    failure = Some(HEALTH_ERR_NOT_RUNNING);
                }

                if let Some(code) = failure {
                    // Invalid attempts preserve the pending request.
                    readiness.last_failure_code = Some(code.to_owned());
                }
            }
        }
    }
    if message_type == Some("goodbye") {
        shared.saw_goodbye.store(true, Ordering::SeqCst);
    }
}

fn spawn_stderr_reader(mut stderr: File, shared: Arc<SupervisorShared>) {
    let _ = thread::Builder::new()
        .name("localcomet-sidecar-stderr".into())
        .spawn(move || {
            let mut buffer = [0_u8; 512];
            loop {
                match stderr.read(&mut buffer) {
                    Ok(0) => break,
                    Ok(count) => {
                        let text = String::from_utf8_lossy(&buffer[..count]);
                        let mut stderr_tail = shared
                            .stderr_tail
                            .lock()
                            .expect("sidecar stderr lock poisoned");
                        stderr_tail.push_str(&limit_text(&text, 1024));
                        if stderr_tail.len() > 4096 {
                            let keep_from = stderr_tail.len() - 4096;
                            stderr_tail.replace_range(..keep_from, "");
                        }
                    }
                    Err(_) => break,
                }
            }
        });
}

#[cfg(debug_assertions)]
fn locate_project_root() -> Option<PathBuf> {
    let mut seeds = Vec::new();
    if let Ok(current_dir) = std::env::current_dir() {
        seeds.push(current_dir);
    }
    if let Ok(current_exe) = std::env::current_exe() {
        seeds.push(current_exe);
    }
    if let Ok(manifest_dir) = std::env::var("CARGO_MANIFEST_DIR") {
        seeds.push(PathBuf::from(manifest_dir));
    }
    for seed in seeds {
        for candidate in seed.ancestors() {
            let root = candidate.to_path_buf();
            if root.join(PYTHON_SIDECAR_RUNNER).is_file()
                && root.join("modules/desktop_sidecar_runtime_ru.py").is_file()
            {
                return Some(root);
            }
        }
    }
    None
}

#[cfg(debug_assertions)]
fn find_python_on_path() -> Option<PathBuf> {
    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        let local_app_data_path = PathBuf::from(&local_app_data);
        let preferred = local_app_data_path.join("Python/pythoncore-3.11-64/python.exe");
        if preferred.is_file() {
            return Some(preferred);
        }
        if let Ok(entries) = std::fs::read_dir(local_app_data_path.join("Python")) {
            let mut candidates: Vec<PathBuf> = entries
                .flatten()
                .map(|entry| entry.path())
                .filter(|path| {
                    path.file_name()
                        .and_then(|s| s.to_str())
                        .map(|s| s.starts_with("pythoncore-"))
                        .unwrap_or(false)
                })
                .collect();
            candidates.sort();
            candidates.reverse();
            for dir in candidates {
                let candidate = dir.join("python.exe");
                if candidate.is_file() {
                    return Some(candidate);
                }
            }
        }
    }
    let path_value = std::env::var_os("PATH")?;
    for base in std::env::split_paths(&path_value) {
        if base
            .to_string_lossy()
            .to_ascii_lowercase()
            .contains("windowsapps")
        {
            // Microsoft Store app-execution-alias stubs exit immediately
            // instead of running a real interpreter; skip them.
            continue;
        }
        for name in ["python.exe", "python3.exe", "py.exe"] {
            let candidate = base.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    if let Ok(program_files) = std::env::var("ProgramFiles") {
        for entry in std::fs::read_dir(&program_files).ok()?.flatten() {
            let path = entry.path();
            if path
                .file_name()
                .and_then(|s| s.to_str())
                .map(|s| s.starts_with("Python"))
                .unwrap_or(false)
            {
                for name in ["python.exe", "python3.exe"] {
                    let candidate = path.join(name);
                    if candidate.is_file() {
                        return Some(candidate);
                    }
                }
            }
        }
    }
    None
}

fn minimal_sidecar_environment(python_exe: Option<&Path>) -> Vec<(OsString, OsString)> {
    let mut env = Vec::new();
    for key in ["SystemRoot", "WINDIR", "TEMP", "TMP"] {
        if let Some(value) = std::env::var_os(key) {
            env.push((OsString::from(key), value));
        }
    }
    env.push((OsString::from("PYTHONUTF8"), OsString::from("1")));
    env.push((OsString::from("PYTHONIOENCODING"), OsString::from("utf-8")));
    env.push((
        OsString::from("PYTHONDONTWRITEBYTECODE"),
        OsString::from("1"),
    ));
    env.push((OsString::from("PYTHONNOUSERSITE"), OsString::from("1")));
    if let Some(value) = std::env::var_os("LOCALCOMET_KNOWLEDGE_VAULT") {
        env.push((OsString::from("LOCALCOMET_KNOWLEDGE_VAULT"), value));
    }
    if let Some(value) = std::env::var_os("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT") {
        env.push((OsString::from("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT"), value));
    }

    let mut path_entries = Vec::new();
    if let Some(parent) = python_exe.and_then(Path::parent) {
        path_entries.push(parent.to_path_buf());
    }
    if let Some(system_root) = std::env::var_os("SystemRoot") {
        path_entries.push(PathBuf::from(system_root).join("System32"));
    }
    if !path_entries.is_empty() {
        let joined = std::env::join_paths(path_entries).unwrap_or_default();
        env.push((OsString::from("PATH"), joined));
    }
    env
}

fn limit_text(text: &str, limit: usize) -> String {
    let cleaned = text.replace('\0', "");
    if cleaned.len() <= limit {
        return cleaned;
    }
    cleaned.chars().take(limit).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Default)]
    struct CountingRouter {
        failures: AtomicU64,
    }

    impl SidecarFrameRouter for CountingRouter {
        fn route_frame(&self, _frame: Vec<u8>) {}

        fn fail_pending(&self, _code: &str, _message: &str) {
            self.failures.fetch_add(1, Ordering::SeqCst);
        }
    }

    /// Resolve the real-sidecar test environment.
    ///
    /// Without LOCALCOMET_TEST_PROJECT_ROOT / LOCALCOMET_TEST_PYTHON the test is
    /// a silent no-op counted as "passed", which makes the suite count
    /// semantically dishonest. When LOCALCOMET_REQUIRE_REAL_SIDECAR is set
    /// (e.g. in CI after installing the sidecar) the absence of the environment
    /// is a hard failure instead of a silent skip.
    fn real_sidecar_env() -> Option<(PathBuf, PathBuf)> {
        let root = std::env::var_os("LOCALCOMET_TEST_PROJECT_ROOT").map(PathBuf::from);
        let python = std::env::var_os("LOCALCOMET_TEST_PYTHON").map(PathBuf::from);
        match (root, python) {
            (Some(root), Some(python)) => Some((root, python)),
            _ => {
                if std::env::var_os("LOCALCOMET_REQUIRE_REAL_SIDECAR").is_some() {
                    panic!(
                        "LOCALCOMET_REQUIRE_REAL_SIDECAR is set but the real-sidecar \
                         environment (LOCALCOMET_TEST_PROJECT_ROOT, LOCALCOMET_TEST_PYTHON) \
                         is not available"
                    );
                }
                eprintln!(
                    "SKIP: real-sidecar test - set LOCALCOMET_TEST_PROJECT_ROOT and \
                     LOCALCOMET_TEST_PYTHON to enable"
                );
                None
            }
        }
    }

    #[test]
    fn debug_launch_spec_uses_fixed_python_runner_arguments() {
        let root = PathBuf::from("LocalCometTest");
        let python = PathBuf::from("Python/python.exe");
        let config = SupervisorConfig::debug_for_tests(root.clone(), python.clone());
        match config.program {
            SidecarProgram::DebugPython {
                python_exe,
                project_root,
                runner,
            } => {
                assert_eq!(python_exe, python);
                assert_eq!(project_root, root);
                assert!(runner.ends_with(PYTHON_SIDECAR_RUNNER));
            }
            _ => panic!("debug Python sidecar expected"),
        }
    }

    #[test]
    fn environment_keeps_only_lifecycle_safe_python_values() {
        let env = minimal_sidecar_environment(Some(Path::new(r"C:\Python\python.exe")));
        let keys: Vec<String> = env
            .iter()
            .map(|(key, _)| key.to_string_lossy().into_owned())
            .collect();
        assert!(keys.contains(&"PYTHONUTF8".to_string()));
        assert!(keys.contains(&"PYTHONIOENCODING".to_string()));
        assert!(keys.contains(&"PYTHONDONTWRITEBYTECODE".to_string()));
        assert!(!keys
            .iter()
            .any(|key| key.contains("TOKEN") || key.contains("SECRET")));
    }

    #[cfg(not(debug_assertions))]
    #[test]
    fn release_config_points_to_future_contained_executable() {
        let config = SupervisorConfig::release_from_current_exe();
        match config.program {
            SidecarProgram::ReleaseBundle {
                executable, runner, ..
            } => {
                assert!(executable.ends_with(RELEASE_SIDECAR_EXE));
                assert!(runner.ends_with(RELEASE_SIDECAR_RUNNER));
            }
            _ => panic!("release sidecar executable expected"),
        }
    }

    #[test]
    fn real_python_sidecar_can_start_when_test_environment_is_present() {
        let Some((root, python)) = real_sidecar_env() else {
            return;
        };
        let supervisor =
            DesktopSidecarSupervisor::new(SupervisorConfig::debug_for_tests(root, python));
        supervisor
            .start_and_wait_ready(Duration::from_secs(5))
            .unwrap();
        let snapshot = supervisor.snapshot();
        assert!(snapshot.running);
        assert!(snapshot.saw_python_hello);
        assert!(snapshot.saw_health_ok);
        supervisor.shutdown().unwrap();
    }

    #[test]
    fn real_sidecar_failed_readiness_stops_the_contained_sidecar() {
        let Some((root, python)) = real_sidecar_env() else {
            return;
        };
        let runner = root.join("tools/test_up00_unready_sidecar.py");
        let config = SupervisorConfig {
            program: SidecarProgram::DebugPython {
                python_exe: python.clone(),
                project_root: root,
                runner,
            },
            env: minimal_sidecar_environment(Some(&python)),
        };
        let supervisor = DesktopSidecarSupervisor::new(config);
        let error = supervisor
            .start_and_wait_ready(Duration::from_millis(150))
            .unwrap_err();
        assert!(matches!(error, SupervisorError::ReadinessTimeout));
        assert!(!supervisor.snapshot().running);
    }

    #[test]
    fn real_sidecar_nonreading_pipe_write_is_bounded_and_releases_supervisor() {
        let Some((root, python)) = real_sidecar_env() else {
            return;
        };
        let runner = root.join("tools/test_up00_unready_sidecar.py");
        let config = SupervisorConfig {
            program: SidecarProgram::DebugPython {
                python_exe: python.clone(),
                project_root: root,
                runner,
            },
            env: minimal_sidecar_environment(Some(&python)),
        };
        let supervisor = DesktopSidecarSupervisor::new(config);
        supervisor.start().unwrap();

        let body = serde_json::json!({
            "protocol": ipc::IPC_PROTOCOL,
            "version": ipc::IPC_PROTOCOL_VERSION,
            "type": "request",
            "id": "desk-timeout-000001",
            "method": HEALTH_METHOD,
            "run_id": null,
            "sequence": 0,
            "reply_to": null,
            "payload": {"padding": "x".repeat(64 * 1024)},
        })
        .to_string();
        let frame = ipc::json_frame(&body).unwrap();
        let started = Instant::now();
        let error = supervisor.send_ipc_frame(frame).unwrap_err();
        assert!(matches!(
            error,
            SupervisorError::Io(ref error) if error.kind() == io::ErrorKind::TimedOut
        ));
        assert!(started.elapsed() < Duration::from_secs(3));
        assert!(!supervisor.snapshot().running);

        let retry_started = Instant::now();
        assert!(matches!(
            supervisor.send_ipc_frame(ipc::desktop_hello_frame("desk-retry", "test").unwrap()),
            Err(SupervisorError::Unavailable(_))
        ));
        assert!(retry_started.elapsed() < Duration::from_millis(100));
    }

    #[test]
    fn lifecycle_frame_observation_requires_exact_health_response_shape() {
        let (shared, request_id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        observe_lifecycle_frame(&r1_response(&request_id, serde_json::json!({})), &shared, 7);
        assert!(shared.saw_python_hello.load(Ordering::SeqCst));
        assert!(shared.saw_health_ok.load(Ordering::SeqCst));

        let other = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"response","reply_to":"desk-other-000000","payload":{"status":"ok"}}"#,
            &other,
            0,
        );
        assert!(!other.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_process_spawn_state_is_not_ready() {
        let (shared, _) = r1_shared_with_pending();
        let readiness = shared.readiness.lock().unwrap();
        assert_ne!(readiness.state, SidecarReadinessState::Ready);
        assert!(!shared.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_ready_requires_correlated_response() {
        let (shared, request_id) = r1_shared_with_pending();
        let mut response = r1_response(&request_id, serde_json::json!({}));
        let mut value: serde_json::Value = serde_json::from_slice(&response).unwrap();
        value["reply_to"] = serde_json::json!("hreq_wrong");
        response = serde_json::to_vec(&value).unwrap();
        observe_lifecycle_frame(&response, &shared, 7);
        assert_ne!(
            shared.readiness.lock().unwrap().state,
            SidecarReadinessState::Ready
        );
    }

    #[test]
    fn p0c_wrong_generation_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let wrong_generation = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","generationId":999,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000","protocolVersion":1,"capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(wrong_generation, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with wrong generationId must not set health ok"
        );
    }

    #[test]
    fn p0c_wrong_nonce_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let wrong_nonce = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","generationId":1,"startupNonce":"scn_ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff","runtimeInstanceId":"rti_00000000000000000000000000000000","protocolVersion":1,"capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(wrong_nonce, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with wrong startupNonce must not set health ok"
        );
    }

    #[test]
    fn p0c_wrong_runtime_instance_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let wrong_rti = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","generationId":1,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_ffffffffffffffffffffffffffffffff","protocolVersion":1,"capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(wrong_rti, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with wrong runtimeInstanceId must not set health ok"
        );
    }

    #[test]
    fn p0c_unknown_request_rejected() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("PendingHealthRegistry"),
            "supervisor must maintain a PendingHealthRegistry to reject unknown request IDs"
        );
    }

    #[test]
    fn p0c_invalid_attempt_preserves_pending_request() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("sidecar_health_generation_mismatch"),
            "supervisor must distinguish generation mismatch without consuming pending request"
        );
    }

    #[test]
    fn p0c_valid_response_completes_once() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("sidecar_health_response_duplicate"),
            "supervisor must distinguish duplicate responses from unknown responses"
        );
    }

    #[test]
    fn p0c_duplicate_response_distinguished() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("HealthCompletion"),
            "supervisor must track one-time completion state for health requests"
        );
    }

    #[test]
    fn p0c_expired_request_rejected() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("PENDING_HEALTH_TTL"),
            "supervisor must enforce a TTL on pending health requests"
        );
    }

    #[test]
    fn p0c_pending_registry_bounded() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("MAX_PENDING_HEALTH_REQUESTS"),
            "pending health registry must be bounded"
        );
    }

    #[test]
    fn p0c_completed_registry_bounded() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("MAX_COMPLETED_HEALTH_TOMBSTONES"),
            "completed health tombstone registry must be bounded"
        );
    }

    #[test]
    fn p0c_oldest_tombstone_evicted_deterministically() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("VecDeque"),
            "tombstone eviction must use oldest-first deterministic ordering"
        );
    }

    #[test]
    fn p0c_process_exit_clears_ready() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("clear_readiness_on_exit"),
            "process exit must immediately clear READY state"
        );
    }

    #[test]
    fn p0c_stop_clears_ready_before_wait() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("SidecarReadinessState::Stopping"),
            "stop must transition to Stopping before waiting for process exit"
        );
    }

    #[test]
    fn p0c_restart_allocates_new_generation() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("SidecarGeneration"),
            "restart must allocate a new SidecarGeneration with incremented generation_id"
        );
    }

    #[test]
    fn p0c_restart_allocates_new_nonce() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("generate_startup_nonce"),
            "restart must generate a fresh startup nonce via CSPRNG"
        );
    }

    #[test]
    fn p0c_restart_rejects_old_response() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("generation_id"),
            "old generation responses must be rejected by generation_id comparison"
        );
    }

    #[test]
    fn p0c_stale_eof_does_not_invalidate_active_generation() {
        let (shared, _) = r1_shared_with_pending();
        shared.saw_python_hello.store(true, Ordering::SeqCst);
        shared.saw_health_ok.store(true, Ordering::SeqCst);
        assert!(!clear_readiness_on_exit(&shared, 6));
        let readiness = shared.readiness.lock().unwrap();
        assert_eq!(readiness.generation.as_ref().unwrap().generation_id, 7);
        assert!(shared.saw_python_hello.load(Ordering::SeqCst));
        assert!(shared.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_stale_frame_does_not_mutate_active_generation() {
        let (shared, id) = r1_shared_with_pending();
        observe_lifecycle_frame(&r1_response(&id, serde_json::json!({})), &shared, 6);
        let readiness = shared.readiness.lock().unwrap();
        assert_eq!(readiness.state, SidecarReadinessState::Stopped);
        assert!(!shared.saw_health_ok.load(Ordering::SeqCst));
        assert!(readiness.health_registry.pending.contains_key(&id));
    }

    #[test]
    fn p0c_protocol_version_mismatch_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let wrong_version = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","protocolVersion":99,"generationId":1,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000","capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(wrong_version, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with protocolVersion=99 must not set health ok"
        );
    }

    #[test]
    fn p0c_tool_execution_true_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let tool_true = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","protocolVersion":1,"generationId":1,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000","capabilities":{"toolExecution":true}}}"#;
        observe_lifecycle_frame(tool_true, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with toolExecution=true must not set health ok"
        );
    }

    #[test]
    fn p0c_tool_execution_missing_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let no_caps = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","protocolVersion":1,"generationId":1,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000"}}"#;
        observe_lifecycle_frame(no_caps, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response without capabilities.toolExecution must not set health ok"
        );
    }

    #[test]
    fn p0c_unknown_status_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let bad_status = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"exploded","protocolVersion":1,"generationId":1,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000","capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(bad_status, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with unknown status must not set health ok"
        );
    }

    #[test]
    fn p0c_frame_too_large_rejected() {
        let result = ipc::json_frame(&"x".repeat(ipc::MAX_FRAME_BYTES + 1));
        assert!(
            result.is_err(),
            "frame exceeding MAX_FRAME_BYTES must be rejected"
        );
    }

    #[test]
    fn p0c_empty_frame_rejected() {
        let result = ipc::json_frame("");
        assert!(result.is_err(), "empty frame must be rejected");
    }

    #[test]
    fn p0c_multiple_objects_rejected() {
        let body = br#"{"a":1}{"b":2}"#;
        let result = ipc::parse_health_frame(body);
        assert!(
            result.is_err(),
            "frame with multiple JSON objects must be rejected"
        );
    }

    #[test]
    fn p0c_duplicate_request_id_key_rejected() {
        let source = include_str!("ipc.rs");
        assert!(
            source.contains("reject_duplicate_keys") || source.contains("duplicate_key"),
            "ipc.rs must reject duplicate JSON keys in health frames"
        );
    }

    #[test]
    fn p0c_duplicate_nonce_key_rejected() {
        let source = include_str!("ipc.rs");
        assert!(
            source.contains("reject_duplicate_keys") || source.contains("duplicate_key"),
            "ipc.rs must reject duplicate startupNonce keys"
        );
    }

    #[test]
    fn p0c_excessive_depth_rejected() {
        let source = include_str!("ipc.rs");
        assert!(
            source.contains("MAX_HEALTH_JSON_DEPTH") || source.contains("max_depth"),
            "ipc.rs must enforce a JSON depth limit for health frames"
        );
    }

    #[test]
    fn p0c_non_integer_generation_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let fractional = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","protocolVersion":1,"generationId":1.5,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000","capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(fractional, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with fractional generationId must not set health ok"
        );
    }

    #[test]
    fn p0c_negative_timestamp_rejected() {
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
            7,
        );
        let negative_ts = br#"{"type":"response","reply_to":"desk-health-000001","payload":{"status":"ok","protocolVersion":1,"generationId":1,"startupNonce":"scn_0000000000000000000000000000000000000000000000000000000000000000","runtimeInstanceId":"rti_00000000000000000000000000000000","receivedAtUnixMs":-1,"capabilities":{"toolExecution":false}}}"#;
        observe_lifecycle_frame(negative_ts, &shared, 7);
        assert!(
            !shared.saw_health_ok.load(Ordering::SeqCst),
            "response with negative receivedAtUnixMs must not set health ok"
        );
    }

    #[test]
    fn p0c_exact_public_error_mapping() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("sidecar_health_timeout"),
            "supervisor must define exact public health error codes"
        );
        assert!(
            source.contains("sidecar_health_nonce_mismatch"),
            "supervisor must define nonce mismatch error code"
        );
        assert!(
            source.contains("sidecar_health_capability_mismatch"),
            "supervisor must define capability mismatch error code"
        );
    }

    #[test]
    fn p0c_health_snapshot_hides_nonce() {
        let source = include_str!("supervisor.rs");
        assert!(
            source.contains("SidecarHealthSnapshot"),
            "supervisor must expose a SidecarHealthSnapshot that excludes startup_nonce"
        );
    }

    #[test]
    fn p0c_p0b_capabilities_remain_absent() {
        let caps = include_str!("../capabilities/main.json");
        assert!(!caps.contains("allow-run-tool-call"));
        assert!(!caps.contains("allow-set-workspace"));
        assert!(!caps.contains("allow-execute-approved"));
    }

    #[test]
    fn p0c_tool_activation_remains_false() {
        let source = include_str!("approval_commands.rs");
        assert!(
            source.contains("const TOOL_EXECUTION_ACTIVATION_ENABLED: bool = false;"),
            "TOOL_EXECUTION_ACTIVATION_ENABLED must remain false"
        );
    }

    #[test]
    fn p0c_shared_malformed_corpus_exists_and_has_required_cases() {
        let corpus_str =
            include_str!("../../../../security/contracts/sidecar_health_malformed_frames_v1.json");
        let corpus: serde_json::Value =
            serde_json::from_str(corpus_str).expect("corpus must parse");
        let cases = corpus["cases"].as_array().expect("cases must be an array");
        assert!(cases.len() >= 15, "corpus must have at least 15 cases");
        let ids: Vec<&str> = cases.iter().filter_map(|c| c["id"].as_str()).collect();
        let required = [
            "duplicate_request_id_key",
            "duplicate_startup_nonce_key",
            "excessive_nesting",
            "oversized_frame",
            "empty_frame",
            "unknown_protocol_version",
            "unknown_status",
            "tool_execution_true",
        ];
        for req in &required {
            assert!(ids.contains(req), "corpus must contain case: {}", req);
        }
    }
    fn r1_shared_with_pending() -> (SupervisorShared, String) {
        let shared = SupervisorShared::default();
        let request_id = "hreq_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_owned();
        let now = unix_time_ms();
        {
            let mut readiness = shared.readiness.lock().unwrap();
            readiness.generation = Some(SidecarGeneration {
                generation_id: 7,
                startup_nonce:
                    "scn_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                        .to_owned(),
                runtime_instance_id: "rti_cccccccccccccccccccccccccccccccc".to_owned(),
            });
            readiness
                .health_registry
                .insert(request_id.clone(), 7, now + 10_000)
                .unwrap();
        }
        (shared, request_id)
    }

    fn r1_response(request_id: &str, payload_updates: serde_json::Value) -> Vec<u8> {
        let mut payload = serde_json::json!({
            "type": "health.status", "protocolVersion": 1, "requestId": request_id,
            "generationId": 7,
            "startupNonce": "scn_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "runtimeInstanceId": "rti_cccccccccccccccccccccccccccccccc", "status": "ready",
            "receivedAtUnixMs": unix_time_ms(), "capabilities": {"toolExecution": false}
        });
        for (key, value) in payload_updates.as_object().unwrap() {
            payload[key] = value.clone();
        }
        serde_json::to_vec(&serde_json::json!({
            "protocol": ipc::IPC_PROTOCOL, "version": ipc::IPC_PROTOCOL_VERSION,
            "type": "response", "id": request_id, "method": null, "run_id": null,
            "sequence": 1, "reply_to": request_id, "payload": payload
        }))
        .unwrap()
    }

    #[test]
    fn p0c_r1_valid_response_reaches_ready() {
        let (shared, id) = r1_shared_with_pending();
        observe_lifecycle_frame(&r1_response(&id, serde_json::json!({})), &shared, 7);
        assert!(shared.saw_health_ok.load(Ordering::SeqCst));
        assert_eq!(
            shared.readiness.lock().unwrap().state,
            SidecarReadinessState::Ready
        );
    }

    #[test]
    fn p0c_r1_invalid_attempt_preserves_pending() {
        let (shared, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(
                &id,
                serde_json::json!({"startupNonce":"scn_ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"}),
            ),
            &shared,
            7,
        );
        observe_lifecycle_frame(&r1_response(&id, serde_json::json!({})), &shared, 7);
        assert!(shared.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_r1_duplicate_distinct_from_unknown() {
        let mut registry = PendingHealthRegistry::default();
        let now = unix_time_ms();
        registry.insert("known".into(), 1, now + 1000).unwrap();
        registry.complete("known", 1, now).unwrap();
        assert_eq!(
            registry.complete("known", 1, now).unwrap_err(),
            HEALTH_ERR_RESPONSE_DUPLICATE
        );
        assert_eq!(
            registry.complete("unknown", 1, now).unwrap_err(),
            HEALTH_ERR_REQUEST_UNKNOWN
        );
    }

    #[test]
    fn p0c_r1_pending_registry_is_bounded() {
        let mut registry = PendingHealthRegistry::default();
        for i in 0..MAX_PENDING_HEALTH_REQUESTS {
            registry
                .insert(format!("id-{i}"), 1, unix_time_ms() + 1000)
                .unwrap();
        }
        assert_eq!(
            registry
                .insert("overflow".into(), 1, unix_time_ms() + 1000)
                .unwrap_err(),
            HEALTH_ERR_FRAME_INVALID
        );
    }

    #[test]
    fn p0c_r1_tombstones_are_bounded() {
        let mut registry = PendingHealthRegistry::default();
        for i in 0..MAX_COMPLETED_HEALTH_TOMBSTONES + 1 {
            let id = format!("id-{i}");
            registry
                .insert(id.clone(), 1, unix_time_ms() + 1000)
                .unwrap();
            registry.complete(&id, 1, unix_time_ms()).unwrap();
            registry.pending.remove(&id);
        }
        assert_eq!(registry.tombstones.len(), MAX_COMPLETED_HEALTH_TOMBSTONES);
        assert!(!registry.is_known_tombstone("id-0"));
    }

    #[test]
    fn p0c_r1_deadline_rejected_without_consuming_pending() {
        let mut registry = PendingHealthRegistry::default();
        registry.insert("id".into(), 1, 10).unwrap();
        assert_eq!(
            registry.complete("id", 1, 11).unwrap_err(),
            HEALTH_ERR_HEALTH_TIMEOUT
        );
        assert_eq!(
            registry.complete("id", 1, 10).unwrap(),
            HealthCompletion::Completed
        );
    }

    #[test]
    fn p0c_r1_registry_generation_mismatch_preserves_pending() {
        let mut registry = PendingHealthRegistry::default();
        registry.insert("id".into(), 2, 100).unwrap();
        assert_eq!(
            registry.complete("id", 1, 10).unwrap_err(),
            HEALTH_ERR_GENERATION_MISMATCH
        );
        assert_eq!(
            registry.complete("id", 2, 10).unwrap(),
            HealthCompletion::Completed
        );
    }

    #[test]
    fn p0c_r1_generation_overflow_fails_closed() {
        let supervisor = DesktopSidecarSupervisor::default();
        supervisor
            .shared
            .generation_counter
            .store(u64::MAX, Ordering::SeqCst);
        let error = supervisor.start().unwrap_err();
        assert!(
            matches!(error, SupervisorError::Unavailable(ref code) if code == HEALTH_ERR_GENERATION_EXHAUSTED)
        );
        assert!(!supervisor.snapshot().running);
        assert_eq!(
            supervisor.shared.readiness.lock().unwrap().state,
            SidecarReadinessState::StartFailed
        );
    }

    #[test]
    fn p0c_write_failure_invalidation_clears_only_matching_generation_and_routes_once() {
        let supervisor = DesktopSidecarSupervisor::default();
        let router = Arc::new(CountingRouter::default());
        supervisor.set_frame_router(router.clone());
        {
            let mut readiness = supervisor.shared.readiness.lock().unwrap();
            readiness.generation = Some(SidecarGeneration {
                generation_id: 7,
                startup_nonce: "nonce".to_owned(),
                runtime_instance_id: "runtime".to_owned(),
            });
            readiness.state = SidecarReadinessState::Ready;
        }

        assert!(!supervisor.invalidate_generation(
            6,
            SidecarReadinessState::StartFailed,
            "sidecar_write_failed",
        ));
        assert_eq!(
            supervisor
                .shared
                .readiness
                .lock()
                .unwrap()
                .generation
                .as_ref()
                .unwrap()
                .generation_id,
            7
        );
        assert_eq!(router.failures.load(Ordering::SeqCst), 0);

        if supervisor.invalidate_generation(
            7,
            SidecarReadinessState::StartFailed,
            "sidecar_write_failed",
        ) {
            supervisor.fail_pending("sidecar_write_failed", "sidecar pipe write failed");
        }
        let readiness = supervisor.shared.readiness.lock().unwrap();
        assert!(readiness.generation.is_none());
        assert_eq!(readiness.state, SidecarReadinessState::StartFailed);
        assert_eq!(
            readiness.last_failure_code.as_deref(),
            Some("sidecar_write_failed")
        );
        assert_eq!(router.failures.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn readiness_failure_mapping_preserves_stable_probe_send_codes() {
        assert_eq!(
            readiness_failure_code(&SupervisorError::Unavailable(
                HEALTH_ERR_HEALTH_TIMEOUT.to_owned()
            )),
            HEALTH_ERR_HEALTH_TIMEOUT
        );
        assert_eq!(
            readiness_failure_code(&SupervisorError::Io(io::Error::new(
                io::ErrorKind::BrokenPipe,
                "sensitive detail",
            ))),
            "sidecar_write_failed"
        );
        assert_eq!(
            readiness_failure_code(&SupervisorError::Unavailable(
                "sensitive_internal_reason".to_owned()
            )),
            HEALTH_ERR_PROBE_SEND_FAILED
        );
    }

    #[test]
    fn p0c_r1_exit_invalidates_generation_and_ready() {
        let (shared, _) = r1_shared_with_pending();
        shared.saw_health_ok.store(true, Ordering::SeqCst);
        clear_readiness_on_exit(&shared, 7);
        let readiness = shared.readiness.lock().unwrap();
        assert!(!shared.saw_health_ok.load(Ordering::SeqCst));
        assert!(readiness.generation.is_none());
        assert_eq!(readiness.state, SidecarReadinessState::Stopped);
    }

    #[test]
    fn p0c_r1_health_request_id_is_cryptographic_shape() {
        let first = generate_health_request_id().expect("csprng available");
        let second = generate_health_request_id().expect("csprng available");
        assert_eq!(first.len(), 37);
        assert!(first.starts_with("hreq_"));
        assert!(first[5..].chars().all(|ch| ch.is_ascii_hexdigit()));
        assert_ne!(first, second);
    }

    #[test]
    fn p0c_r1_outer_id_mismatch_does_not_ready() {
        let (shared, id) = r1_shared_with_pending();
        let mut value: serde_json::Value =
            serde_json::from_slice(&r1_response(&id, serde_json::json!({}))).unwrap();
        value["id"] = serde_json::json!("hreq_dddddddddddddddddddddddddddddddd");
        observe_lifecycle_frame(&serde_json::to_vec(&value).unwrap(), &shared, 7);
        assert!(!shared.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_r1_reply_to_mismatch_does_not_ready() {
        let (shared, id) = r1_shared_with_pending();
        let mut value: serde_json::Value =
            serde_json::from_slice(&r1_response(&id, serde_json::json!({}))).unwrap();
        value["reply_to"] = serde_json::json!("hreq_dddddddddddddddddddddddddddddddd");
        observe_lifecycle_frame(&serde_json::to_vec(&value).unwrap(), &shared, 7);
        assert!(!shared.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_r1_status_must_be_ready() {
        let (s, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(&id, serde_json::json!({"status":"degraded"})),
            &s,
            7,
        );
        assert!(!s.saw_health_ok.load(Ordering::SeqCst));
    }
    #[test]
    fn p0c_r1_tool_execution_true_does_not_ready() {
        let (s, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(
                &id,
                serde_json::json!({"capabilities":{"toolExecution":true}}),
            ),
            &s,
            7,
        );
        assert!(!s.saw_health_ok.load(Ordering::SeqCst));
    }
    #[test]
    fn p0c_r1_wrong_generation_does_not_ready() {
        let (s, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(&id, serde_json::json!({"generationId":8})),
            &s,
            7,
        );
        assert!(!s.saw_health_ok.load(Ordering::SeqCst));
    }
    #[test]
    fn p0c_r1_wrong_runtime_does_not_ready() {
        let (s, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(
                &id,
                serde_json::json!({"runtimeInstanceId":"rti_dddddddddddddddddddddddddddddddd"}),
            ),
            &s,
            7,
        );
        assert!(!s.saw_health_ok.load(Ordering::SeqCst));
    }
    #[test]
    fn p0c_r1_negative_timestamp_does_not_ready() {
        let (s, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(&id, serde_json::json!({"receivedAtUnixMs":-1})),
            &s,
            7,
        );
        assert!(!s.saw_health_ok.load(Ordering::SeqCst));
    }
    #[test]
    fn p0c_r1_protocol_mismatch_does_not_ready() {
        let (s, id) = r1_shared_with_pending();
        observe_lifecycle_frame(
            &r1_response(&id, serde_json::json!({"protocolVersion":2})),
            &s,
            7,
        );
        assert!(!s.saw_health_ok.load(Ordering::SeqCst));
    }

    #[test]
    fn p0c_r1_shared_parser_corpus_runs_every_parser_case() {
        let corpus: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../security/contracts/sidecar_health_malformed_frames_v1.json"
        ))
        .unwrap();
        let cases: Vec<&serde_json::Value> = corpus["cases"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|case| case["parser_reject"] == true)
            .collect();
        assert!(cases.len() >= 12);
        for case in cases {
            let body = if case["invalid_utf8"] == true {
                vec![b'{', b'"', b'x', b'"', b':', b'"', 0xff, b'"', b'}']
            } else if let Some(size) = case["size_bytes"].as_u64() {
                vec![b'x'; size as usize]
            } else if let Some(depth) = case["depth"].as_u64() {
                format!(
                    "{}0{}",
                    "[".repeat(depth as usize),
                    "]".repeat(depth as usize)
                )
                .into_bytes()
            } else {
                case["json"].as_str().unwrap().as_bytes().to_vec()
            };
            assert!(
                ipc::parse_health_frame(&body).is_err(),
                "corpus case accepted: {}",
                case["id"]
            );
        }
    }

    #[test]
    fn p0c_r1_repeated_array_values_are_accepted_on_production_seam() {
        assert!(ipc::parse_health_frame(br#"{"tags":["x","x"]}"#).is_ok());
    }
    #[test]
    fn p0c_r1_decoded_unicode_duplicate_rejected_on_production_seam() {
        assert_eq!(
            ipc::parse_health_frame(br#"{"status":1,"st\u0061tus":2}"#).unwrap_err(),
            "duplicate_key"
        );
    }
    #[test]
    fn p0c_r1_capability_boundary_remains_closed() {
        let caps = include_str!("../capabilities/main.json");
        for forbidden in [
            "allow-run-tool-call",
            "allow-set-workspace",
            "allow-execute-approved",
        ] {
            assert!(!caps.contains(forbidden));
        }
        assert!(include_str!("approval_commands.rs")
            .contains("const TOOL_EXECUTION_ACTIVATION_ENABLED: bool = false;"));
    }
}
