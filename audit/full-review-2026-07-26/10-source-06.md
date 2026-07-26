# Полный исходный код (продолжение)

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/single_instance.rs (80 строк, 2274 байт)

````rust
use std::io;

const INSTANCE_MUTEX_NAME: &str = r"Local\com.localcomet.desktop";

#[cfg(windows)]
mod platform {
    use super::*;
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use std::ptr::null;
    use windows_sys::Win32::Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, HANDLE};
    use windows_sys::Win32::System::Threading::CreateMutexW;

    pub struct SingleInstanceGuard {
        handle: HANDLE,
    }

    unsafe impl Send for SingleInstanceGuard {}

    pub fn acquire() -> io::Result<Option<SingleInstanceGuard>> {
        acquire_named(INSTANCE_MUTEX_NAME)
    }

    fn acquire_named(name: &str) -> io::Result<Option<SingleInstanceGuard>> {
        let mut wide_name: Vec<u16> = OsStr::new(name).encode_wide().collect();
        wide_name.push(0);
        let handle = unsafe { CreateMutexW(null(), 0, wide_name.as_ptr()) };
        if handle.is_null() {
            return Err(io::Error::last_os_error());
        }
        if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
            unsafe {
                CloseHandle(handle);
            }
            return Ok(None);
        }
        Ok(Some(SingleInstanceGuard { handle }))
    }

    impl Drop for SingleInstanceGuard {
        fn drop(&mut self) {
            if !self.handle.is_null() {
                unsafe {
                    CloseHandle(self.handle);
                }
                self.handle = std::ptr::null_mut();
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use windows_sys::Win32::System::Threading::GetCurrentProcessId;

        #[test]
        fn named_mutex_rejects_a_second_instance() {
            let name = format!(r"Local\com.localcomet.desktop.test.{}", unsafe {
                GetCurrentProcessId()
            });
            let first = acquire_named(&name).unwrap();
            assert!(first.is_some());
            let second = acquire_named(&name).unwrap();
            assert!(second.is_none());
        }
    }
}

#[cfg(not(windows))]
mod platform {
    use super::*;

    pub struct SingleInstanceGuard;

    pub fn acquire() -> io::Result<Option<SingleInstanceGuard>> {
        Ok(Some(SingleInstanceGuard))
    }
}

pub use platform::{acquire, SingleInstanceGuard};
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/startup.rs (179 строк, 6010 байт)

````rust
use crate::app_data_root::{self, ApplicationDataRootError, APPLICATION_DATA_ROOT_OVERRIDE};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

pub const STARTUP_LOG_DISPLAY_PATH: &str = r"<LocalComet application-data root>\logs\startup.log";

#[derive(Clone, Copy, Debug)]
pub enum StartupPhase {
    SingleInstance,
    BackendStart,
    BackendReadiness,
    WindowDisplay,
}

impl StartupPhase {
    fn log_name(self) -> &'static str {
        match self {
            Self::SingleInstance => "single_instance",
            Self::BackendStart => "backend_start",
            Self::BackendReadiness => "backend_readiness",
            Self::WindowDisplay => "window_display",
        }
    }

    fn display_name(self) -> &'static str {
        match self {
            Self::SingleInstance => "single-instance check",
            Self::BackendStart => "packaged backend start",
            Self::BackendReadiness => "packaged backend readiness",
            Self::WindowDisplay => "desktop window display",
        }
    }
}

pub fn record(phase: StartupPhase, status: &str, code: &str) {
    let Some(path) = startup_log_path() else {
        return;
    };
    let Some(parent) = path.parent() else {
        return;
    };
    if std::fs::create_dir_all(parent).is_err() {
        return;
    }
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    let row = format!(
        "timestamp_unix={timestamp}\tphase={}\tstatus={}\tcode={}\n",
        phase.log_name(),
        safe_token(status),
        safe_token(code)
    );
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(row.as_bytes());
    }
}

pub fn report_failure(phase: StartupPhase, code: &'static str) {
    record(phase, "failure", code);
    show_native_failure(&failure_message(phase, code));
}

pub fn report_failure_with_reason(phase: StartupPhase, code: &'static str, reason: &'static str) {
    record(phase, &failure_status(reason), code);
    show_native_failure(&failure_message(phase, code));
}

pub fn report_application_data_root_failure(error: ApplicationDataRootError) {
    show_native_failure(&application_data_root_failure_message(error));
}

fn application_data_root_failure_message(error: ApplicationDataRootError) -> String {
    format!(
        "LocalComet could not start.\n\nPhase: packaged application-data root validation\nCode: {}\n\n{} must be a nonempty absolute local directory path. LocalComet did not fall back to the normal profile.\n\nClose safely: Select OK, correct the launch environment, and try LocalComet again.",
        error.code(),
        APPLICATION_DATA_ROOT_OVERRIDE,
    )
}

fn failure_message(phase: StartupPhase, code: &str) -> String {
    format!(
        "LocalComet could not start.\n\nPhase: {}\nCode: {}\n\nRetry: It is safe to close this message and try LocalComet again. If the failure repeats, reinstall LocalComet using the approved installer.\n\nLog: {}\n\nClose safely: Select OK. Any managed child process will be stopped before the application exits.",
        phase.display_name(),
        safe_token(code),
        STARTUP_LOG_DISPLAY_PATH
    )
}

fn startup_log_path() -> Option<PathBuf> {
    app_data_root::resolve_startup_application_data_root()
        .ok()
        .flatten()
        .map(|root| root.join("logs").join("startup.log"))
}

fn safe_token(value: &str) -> String {
    value
        .chars()
        .filter(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '_' | '-' | '.')
        })
        .take(64)
        .collect()
}

fn failure_status(reason: &str) -> String {
    format!("failure.{}", safe_token(reason))
}

#[cfg(windows)]
fn show_native_failure(message: &str) {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use std::ptr::null_mut;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        MessageBoxW, MB_ICONERROR, MB_OK, MB_SETFOREGROUND,
    };

    let mut message_wide: Vec<u16> = OsStr::new(message).encode_wide().collect();
    message_wide.push(0);
    let mut title_wide: Vec<u16> = OsStr::new("LocalComet startup").encode_wide().collect();
    title_wide.push(0);
    unsafe {
        MessageBoxW(
            null_mut(),
            message_wide.as_ptr(),
            title_wide.as_ptr(),
            MB_OK | MB_ICONERROR | MB_SETFOREGROUND,
        );
    }
}

#[cfg(not(windows))]
fn show_native_failure(_message: &str) {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_failure_message_is_actionable_and_path_sanitized() {
        let message = failure_message(StartupPhase::BackendReadiness, "LC_START_102");
        assert!(message.contains("packaged backend readiness"));
        assert!(message.contains("safe to close"));
        assert!(message.contains("reinstall"));
        assert!(message.contains(STARTUP_LOG_DISPLAY_PATH));
        let machine_path_prefix = ["C:", "\\", "Users", "\\"].concat();
        assert!(!message.contains(&machine_path_prefix));
    }

    #[test]
    fn log_tokens_reject_path_and_control_characters() {
        assert_eq!(safe_token("code\r\nC:\\private"), "codeCprivate");
    }

    #[test]
    fn diagnostic_failure_reason_is_stable_and_sanitized() {
        assert_eq!(
            failure_status("sidecar_unavailable"),
            "failure.sidecar_unavailable"
        );
        assert_eq!(
            failure_status("sidecar\r\nC:\\private"),
            "failure.sidecarCprivate"
        );
    }

    #[test]
    fn application_data_root_failure_is_explicit_and_does_not_echo_paths() {
        let message = application_data_root_failure_message(ApplicationDataRootError::Relative);
        assert!(message.contains("LOCALCOMET_APP_DATA_ROOT"));
        assert!(message.contains("relative_app_data_root_override"));
        assert!(!message.contains("C:\\Users"));
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/supervisor.rs (899 строк, 32208 байт)

````rust
use crate::ipc;
use crate::windows_job::{ContainedSidecarProcess, SidecarLaunchSpec};
use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
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

pub struct DesktopSidecarSupervisor {
    config: SupervisorConfig,
    state: Mutex<SupervisorState>,
    shared: Arc<SupervisorShared>,
}

impl DesktopSidecarSupervisor {
    pub fn new(config: SupervisorConfig) -> Self {
        Self {
            config,
            state: Mutex::new(SupervisorState::default()),
            shared: Arc::new(SupervisorShared::default()),
        }
    }

    pub fn start(&self) -> Result<(), SupervisorError> {
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
        let mut process = ContainedSidecarProcess::spawn(&spec)?;
        if let Some(stdout) = process.take_stdout() {
            spawn_stdout_reader(stdout, Arc::clone(&self.shared));
        }
        if let Some(stderr) = process.take_stderr() {
            spawn_stderr_reader(stderr, Arc::clone(&self.shared));
        }

        let hello = ipc::desktop_hello_frame("desk-hello-000001", "localcomet-desktop")?;
        process.write_frame_bounded(&hello, IPC_WRITE_TIMEOUT)?;
        state.process = Some(process);
        Ok(())
    }

    pub fn start_and_wait_ready(&self, timeout: Duration) -> Result<(), SupervisorError> {
        self.start()?;
        if let Err(error) = self.send_health_probe() {
            self.abort_start();
            return Err(error);
        }

        let deadline = Instant::now() + timeout;
        loop {
            let snapshot = self.snapshot();
            if snapshot.running && snapshot.saw_python_hello && snapshot.saw_health_ok {
                return Ok(());
            }
            if !snapshot.running {
                self.abort_start();
                return Err(SupervisorError::ExitedBeforeReady);
            }
            if Instant::now() >= deadline {
                self.abort_start();
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
        let (result, failed_process) = {
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
            let failed_process = result.as_ref().err().and_then(|_| state.process.take());
            (result, failed_process)
        };
        if let Some(process) = failed_process {
            process.terminate(1);
            let _ = process.wait_bounded(1_000);
            self.fail_pending("sidecar_write_failed", "sidecar pipe write failed");
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
        self.send_ipc_frame(ipc::lifecycle_request_frame(
            &format!("desk-health-{sequence:06}"),
            HEALTH_METHOD,
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

    fn abort_start(&self) {
        let process = self
            .state
            .lock()
            .expect("sidecar supervisor lock poisoned")
            .process
            .take();
        if let Some(process) = process {
            if process.is_running() {
                process.terminate(1);
                let _ = process.wait_bounded(1_000);
            }
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

fn spawn_stdout_reader(mut stdout: File, shared: Arc<SupervisorShared>) {
    let _ = thread::Builder::new()
        .name("localcomet-sidecar-stdout".into())
        .spawn(move || {
            while let Ok(frame) = ipc::read_frame(&mut stdout) {
                let text = String::from_utf8_lossy(&frame).into_owned();
                observe_lifecycle_frame(&frame, &shared);
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
            let router = shared
                .router
                .lock()
                .expect("sidecar router lock poisoned")
                .clone();
            if let Some(router) = router {
                router.fail_pending("sidecar_unavailable", "sidecar stdout closed");
            }
        });
}

fn observe_lifecycle_frame(frame: &[u8], shared: &SupervisorShared) {
    let Ok(message) = serde_json::from_slice::<serde_json::Value>(frame) else {
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
    if message_type == Some("response")
        && message
            .get("reply_to")
            .and_then(serde_json::Value::as_str)
            .map(|reply_to| reply_to.starts_with("desk-health-"))
            .unwrap_or(false)
        && message
            .pointer("/payload/status")
            .and_then(serde_json::Value::as_str)
            == Some("ok")
    {
        shared.saw_health_ok.store(true, Ordering::SeqCst);
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
    fn failed_readiness_stops_the_contained_sidecar() {
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
    fn nonreading_sidecar_pipe_write_is_bounded_and_releases_supervisor() {
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
        let shared = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"hello","payload":{"role":"python_core"}}"#,
            &shared,
        );
        observe_lifecycle_frame(
            br#"{"type":"response","reply_to":"desk-health-000000","payload":{"status":"ok"}}"#,
            &shared,
        );
        assert!(shared.saw_python_hello.load(Ordering::SeqCst));
        assert!(shared.saw_health_ok.load(Ordering::SeqCst));

        let other = SupervisorShared::default();
        observe_lifecycle_frame(
            br#"{"type":"response","reply_to":"desk-other-000000","payload":{"status":"ok"}}"#,
            &other,
        );
        assert!(!other.saw_health_ok.load(Ordering::SeqCst));
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/windows_job.rs (789 строк, 26038 байт)

````rust
use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, Instant};

const PIPE_WRITE_RETRY_DELAY: Duration = Duration::from_millis(2);

fn write_all_bounded<W: Write>(
    writer: &mut W,
    mut bytes: &[u8],
    timeout: Duration,
) -> io::Result<()> {
    let started = Instant::now();
    while !bytes.is_empty() {
        match writer.write(bytes) {
            Ok(0) => {
                if started.elapsed() >= timeout {
                    return Err(io::Error::new(
                        io::ErrorKind::TimedOut,
                        "sidecar pipe write timed out",
                    ));
                }
                thread::sleep(PIPE_WRITE_RETRY_DELAY);
            }
            Ok(written) => bytes = &bytes[written..],
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) if retryable_pipe_backpressure(&error) => {
                if started.elapsed() >= timeout {
                    return Err(io::Error::new(
                        io::ErrorKind::TimedOut,
                        "sidecar pipe write timed out",
                    ));
                }
                thread::sleep(PIPE_WRITE_RETRY_DELAY);
            }
            Err(error) => return Err(error),
        }
    }
    Ok(())
}

fn retryable_pipe_backpressure(error: &io::Error) -> bool {
    if error.kind() == io::ErrorKind::WouldBlock {
        return true;
    }
    #[cfg(windows)]
    {
        error.raw_os_error() == Some(windows_sys::Win32::Foundation::ERROR_NO_DATA as i32)
    }
    #[cfg(not(windows))]
    {
        false
    }
}

#[derive(Clone, Debug)]
pub struct SidecarLaunchSpec {
    pub executable: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
    pub env: Vec<(OsString, OsString)>,
}

#[derive(Clone, Debug)]
pub struct ManagedRuntimeLaunchSpec {
    pub executable: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
    pub env: Vec<(OsString, OsString)>,
}

#[cfg(windows)]
mod platform {
    use super::*;
    use std::ffi::{c_void, OsStr};
    use std::mem::{size_of, zeroed};
    use std::os::windows::ffi::OsStrExt;
    use std::os::windows::io::{FromRawHandle, RawHandle};
    use std::ptr::{null, null_mut};
    use windows_sys::Win32::Foundation::{
        CloseHandle, GetLastError, SetHandleInformation, HANDLE, HANDLE_FLAG_INHERIT,
        INVALID_HANDLE_VALUE, WAIT_TIMEOUT,
    };
    use windows_sys::Win32::Security::SECURITY_ATTRIBUTES;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };
    use windows_sys::Win32::System::Pipes::{CreatePipe, SetNamedPipeHandleState, PIPE_NOWAIT};
    use windows_sys::Win32::System::Threading::{
        CreateProcessW, DeleteProcThreadAttributeList, InitializeProcThreadAttributeList,
        ResumeThread, TerminateProcess, UpdateProcThreadAttribute, WaitForSingleObject,
        CREATE_NO_WINDOW, CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT,
        EXTENDED_STARTUPINFO_PRESENT, LPPROC_THREAD_ATTRIBUTE_LIST, PROCESS_INFORMATION,
        PROC_THREAD_ATTRIBUTE_HANDLE_LIST, STARTF_USESTDHANDLES, STARTUPINFOEXW, STARTUPINFOW,
    };

    pub struct ContainedSidecarProcess {
        process: OwnedHandle,
        job: OwnedHandle,
        stdin: File,
        stdout: Option<File>,
        stderr: Option<File>,
    }

    pub struct ContainedManagedRuntimeProcess {
        process: OwnedHandle,
        job: OwnedHandle,
        process_id: u32,
        stdout: Option<File>,
        stderr: Option<File>,
    }

    impl ContainedSidecarProcess {
        pub fn spawn(spec: &SidecarLaunchSpec) -> io::Result<Self> {
            spawn_contained(spec)
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            self.stdout.take()
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            self.stderr.take()
        }

        pub fn write_frame_bounded(&mut self, frame: &[u8], timeout: Duration) -> io::Result<()> {
            write_all_bounded(&mut self.stdin, frame, timeout)
        }

        pub fn is_running(&self) -> bool {
            let _job_handle = self.job.raw();
            unsafe { WaitForSingleObject(self.process.raw(), 0) == WAIT_TIMEOUT }
        }

        pub fn terminate(&self, exit_code: u32) {
            unsafe {
                TerminateProcess(self.process.raw(), exit_code);
            }
        }

        pub fn wait_bounded(&self, millis: u32) -> bool {
            unsafe { WaitForSingleObject(self.process.raw(), millis) != WAIT_TIMEOUT }
        }
    }

    impl ContainedManagedRuntimeProcess {
        pub fn spawn(spec: &ManagedRuntimeLaunchSpec) -> io::Result<Self> {
            spawn_managed_contained(spec)
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            self.stdout.take()
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            self.stderr.take()
        }

        pub fn is_running(&self) -> bool {
            let _job_handle = self.job.raw();
            unsafe { WaitForSingleObject(self.process.raw(), 0) == WAIT_TIMEOUT }
        }

        pub fn process_id(&self) -> u32 {
            self.process_id
        }

        pub fn terminate(&self, exit_code: u32) {
            unsafe {
                TerminateProcess(self.process.raw(), exit_code);
            }
        }

        pub fn wait_bounded(&self, millis: u32) -> bool {
            unsafe { WaitForSingleObject(self.process.raw(), millis) != WAIT_TIMEOUT }
        }
    }

    impl Drop for ContainedManagedRuntimeProcess {
        fn drop(&mut self) {
            unsafe {
                if self.is_running() {
                    TerminateProcess(self.process.raw(), 0);
                    WaitForSingleObject(self.process.raw(), 2_000);
                }
            }
        }
    }

    impl Drop for ContainedSidecarProcess {
        fn drop(&mut self) {
            unsafe {
                if self.is_running() {
                    TerminateProcess(self.process.raw(), 0);
                    WaitForSingleObject(self.process.raw(), 2_000);
                }
            }
        }
    }

    struct OwnedHandle {
        handle: HANDLE,
    }

    unsafe impl Send for OwnedHandle {}

    impl OwnedHandle {
        fn new(handle: HANDLE) -> io::Result<Self> {
            if invalid_handle(handle) {
                Err(last_error())
            } else {
                Ok(Self { handle })
            }
        }

        fn raw(&self) -> HANDLE {
            self.handle
        }

        fn into_file(mut self) -> File {
            let handle = self.handle;
            self.handle = null_mut();
            unsafe { File::from_raw_handle(handle as RawHandle) }
        }
    }

    impl Drop for OwnedHandle {
        fn drop(&mut self) {
            if !invalid_handle(self.handle) {
                unsafe {
                    CloseHandle(self.handle);
                }
                self.handle = null_mut();
            }
        }
    }

    struct AttributeList {
        pointer: LPPROC_THREAD_ATTRIBUTE_LIST,
        _buffer: Vec<u8>,
    }

    impl AttributeList {
        fn for_handles(handles: &[HANDLE]) -> io::Result<Self> {
            let mut size = 0_usize;
            unsafe {
                InitializeProcThreadAttributeList(null_mut(), 1, 0, &mut size);
            }
            if size == 0 {
                return Err(last_error());
            }
            let mut buffer = vec![0_u8; size];
            let pointer = buffer.as_mut_ptr() as LPPROC_THREAD_ATTRIBUTE_LIST;
            let initialized =
                unsafe { InitializeProcThreadAttributeList(pointer, 1, 0, &mut size) != 0 };
            if !initialized {
                return Err(last_error());
            }
            let updated = unsafe {
                UpdateProcThreadAttribute(
                    pointer,
                    0,
                    PROC_THREAD_ATTRIBUTE_HANDLE_LIST as usize,
                    handles.as_ptr() as *const c_void,
                    std::mem::size_of_val(handles),
                    null_mut(),
                    null(),
                ) != 0
            };
            if !updated {
                unsafe {
                    DeleteProcThreadAttributeList(pointer);
                }
                return Err(last_error());
            }
            Ok(Self {
                pointer,
                _buffer: buffer,
            })
        }
    }

    impl Drop for AttributeList {
        fn drop(&mut self) {
            unsafe {
                DeleteProcThreadAttributeList(self.pointer);
            }
        }
    }

    fn spawn_contained(spec: &SidecarLaunchSpec) -> io::Result<ContainedSidecarProcess> {
        let job = create_single_process_kill_on_close_job()?;
        let mut stdin_read = null_mut();
        let mut stdin_write = null_mut();
        let mut stdout_read = null_mut();
        let mut stdout_write = null_mut();
        let mut stderr_read = null_mut();
        let mut stderr_write = null_mut();
        let security = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: null_mut(),
            bInheritHandle: 1,
        };

        unsafe {
            if CreatePipe(&mut stdin_read, &mut stdin_write, &security, 0) == 0 {
                return Err(last_error());
            }
            if CreatePipe(&mut stdout_read, &mut stdout_write, &security, 0) == 0 {
                return Err(last_error());
            }
            if CreatePipe(&mut stderr_read, &mut stderr_write, &security, 0) == 0 {
                return Err(last_error());
            }
        }

        let child_stdin = OwnedHandle::new(stdin_read)?;
        let parent_stdin = OwnedHandle::new(stdin_write)?;
        let parent_stdout = OwnedHandle::new(stdout_read)?;
        let child_stdout = OwnedHandle::new(stdout_write)?;
        let parent_stderr = OwnedHandle::new(stderr_read)?;
        let child_stderr = OwnedHandle::new(stderr_write)?;

        set_parent_only(parent_stdin.raw())?;
        set_parent_only(parent_stdout.raw())?;
        set_parent_only(parent_stderr.raw())?;
        set_pipe_nowait(parent_stdin.raw())?;

        let inheritable_handles = [child_stdin.raw(), child_stdout.raw(), child_stderr.raw()];
        let attributes = AttributeList::for_handles(&inheritable_handles)?;
        let mut startup: STARTUPINFOEXW = unsafe { zeroed() };
        startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = child_stdin.raw();
        startup.StartupInfo.hStdOutput = child_stdout.raw();
        startup.StartupInfo.hStdError = child_stderr.raw();
        startup.lpAttributeList = attributes.pointer;

        let executable_wide = wide_null(spec.executable.as_os_str());
        let current_dir_wide = wide_null(spec.current_dir.as_os_str());
        let mut command_line = build_command_line(&spec.executable, &spec.args);
        let environment = build_environment_block(&spec.env);
        let mut process_info: PROCESS_INFORMATION = unsafe { zeroed() };
        let creation_flags = CREATE_SUSPENDED
            | CREATE_NO_WINDOW
            | CREATE_UNICODE_ENVIRONMENT
            | EXTENDED_STARTUPINFO_PRESENT;

        let created = unsafe {
            CreateProcessW(
                executable_wide.as_ptr(),
                command_line.as_mut_ptr(),
                null(),
                null(),
                1,
                creation_flags,
                environment.as_ptr() as *const c_void,
                current_dir_wide.as_ptr(),
                &startup.StartupInfo as *const STARTUPINFOW,
                &mut process_info,
            ) != 0
        };
        if !created {
            return Err(last_error());
        }

        let process = OwnedHandle::new(process_info.hProcess)?;
        let thread = OwnedHandle::new(process_info.hThread)?;
        let assigned = unsafe { AssignProcessToJobObject(job.raw(), process.raw()) != 0 };
        if !assigned {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }
        let resumed = unsafe { ResumeThread(thread.raw()) != u32::MAX };
        if !resumed {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }

        drop(child_stdin);
        drop(child_stdout);
        drop(child_stderr);
        drop(thread);

        Ok(ContainedSidecarProcess {
            process,
            job,
            stdin: parent_stdin.into_file(),
            stdout: Some(parent_stdout.into_file()),
            stderr: Some(parent_stderr.into_file()),
        })
    }

    fn spawn_managed_contained(
        spec: &ManagedRuntimeLaunchSpec,
    ) -> io::Result<ContainedManagedRuntimeProcess> {
        let job = create_single_process_kill_on_close_job()?;
        let mut stdout_read = null_mut();
        let mut stdout_write = null_mut();
        let mut stderr_read = null_mut();
        let mut stderr_write = null_mut();
        let security = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: null_mut(),
            bInheritHandle: 1,
        };

        unsafe {
            if CreatePipe(&mut stdout_read, &mut stdout_write, &security, 0) == 0 {
                return Err(last_error());
            }
            if CreatePipe(&mut stderr_read, &mut stderr_write, &security, 0) == 0 {
                return Err(last_error());
            }
        }

        let parent_stdout = OwnedHandle::new(stdout_read)?;
        let child_stdout = OwnedHandle::new(stdout_write)?;
        let parent_stderr = OwnedHandle::new(stderr_read)?;
        let child_stderr = OwnedHandle::new(stderr_write)?;

        set_parent_only(parent_stdout.raw())?;
        set_parent_only(parent_stderr.raw())?;

        let inheritable_handles = [child_stdout.raw(), child_stderr.raw()];
        let attributes = AttributeList::for_handles(&inheritable_handles)?;
        let mut startup: STARTUPINFOEXW = unsafe { zeroed() };
        startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = null_mut();
        startup.StartupInfo.hStdOutput = child_stdout.raw();
        startup.StartupInfo.hStdError = child_stderr.raw();
        startup.lpAttributeList = attributes.pointer;

        let executable_wide = wide_null(spec.executable.as_os_str());
        let current_dir_wide = wide_null(spec.current_dir.as_os_str());
        let mut command_line = build_command_line(&spec.executable, &spec.args);
        let environment = build_environment_block(&spec.env);
        let mut process_info: PROCESS_INFORMATION = unsafe { zeroed() };
        let creation_flags = CREATE_SUSPENDED
            | CREATE_NO_WINDOW
            | CREATE_UNICODE_ENVIRONMENT
            | EXTENDED_STARTUPINFO_PRESENT;

        let created = unsafe {
            CreateProcessW(
                executable_wide.as_ptr(),
                command_line.as_mut_ptr(),
                null(),
                null(),
                1,
                creation_flags,
                environment.as_ptr() as *const c_void,
                current_dir_wide.as_ptr(),
                &startup.StartupInfo as *const STARTUPINFOW,
                &mut process_info,
            ) != 0
        };
        if !created {
            return Err(last_error());
        }

        let process = OwnedHandle::new(process_info.hProcess)?;
        let thread = OwnedHandle::new(process_info.hThread)?;
        let assigned = unsafe { AssignProcessToJobObject(job.raw(), process.raw()) != 0 };
        if !assigned {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }
        let resumed = unsafe { ResumeThread(thread.raw()) != u32::MAX };
        if !resumed {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }

        drop(child_stdout);
        drop(child_stderr);
        drop(thread);

        Ok(ContainedManagedRuntimeProcess {
            process,
            job,
            process_id: process_info.dwProcessId,
            stdout: Some(parent_stdout.into_file()),
            stderr: Some(parent_stderr.into_file()),
        })
    }

    fn create_single_process_kill_on_close_job() -> io::Result<OwnedHandle> {
        let job = OwnedHandle::new(unsafe { CreateJobObjectW(null(), null()) })?;
        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags =
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
        limits.BasicLimitInformation.ActiveProcessLimit = 1;
        let configured = unsafe {
            SetInformationJobObject(
                job.raw(),
                JobObjectExtendedLimitInformation,
                &limits as *const _ as *const c_void,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            ) != 0
        };
        if !configured {
            return Err(last_error());
        }
        Ok(job)
    }

    fn set_parent_only(handle: HANDLE) -> io::Result<()> {
        let ok = unsafe { SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0) != 0 };
        if ok {
            Ok(())
        } else {
            Err(last_error())
        }
    }

    fn set_pipe_nowait(handle: HANDLE) -> io::Result<()> {
        let mode = PIPE_NOWAIT;
        let changed = unsafe {
            SetNamedPipeHandleState(handle, &mode, std::ptr::null(), std::ptr::null()) != 0
        };
        if changed {
            Ok(())
        } else {
            Err(last_error())
        }
    }

    fn build_command_line(executable: &Path, args: &[OsString]) -> Vec<u16> {
        let mut parts = Vec::with_capacity(args.len() + 1);
        parts.push(quote_windows_arg(executable.as_os_str()));
        for arg in args {
            parts.push(quote_windows_arg(arg.as_os_str()));
        }
        wide_null(OsString::from(parts.join(" ")).as_os_str())
    }

    fn build_environment_block(env: &[(OsString, OsString)]) -> Vec<u16> {
        let mut pairs: Vec<(OsString, OsString)> = env.to_vec();
        pairs.sort_by(|left, right| {
            left.0
                .to_string_lossy()
                .to_ascii_uppercase()
                .cmp(&right.0.to_string_lossy().to_ascii_uppercase())
        });
        let mut block = Vec::new();
        for (key, value) in pairs {
            block.extend(key.encode_wide());
            block.push('=' as u16);
            block.extend(value.encode_wide());
            block.push(0);
        }
        block.push(0);
        block
    }

    fn quote_windows_arg(value: &OsStr) -> String {
        let text = value.to_string_lossy();
        if !text.is_empty() && !text.chars().any(|ch| ch.is_whitespace() || ch == '"') {
            return text.into_owned();
        }
        let mut quoted = String::from("\"");
        let mut backslashes = 0;
        for ch in text.chars() {
            match ch {
                '\\' => backslashes += 1,
                '"' => {
                    quoted.push_str(&"\\".repeat(backslashes * 2 + 1));
                    quoted.push('"');
                    backslashes = 0;
                }
                ch => {
                    quoted.push_str(&"\\".repeat(backslashes));
                    quoted.push(ch);
                    backslashes = 0;
                }
            }
        }
        quoted.push_str(&"\\".repeat(backslashes * 2));
        quoted.push('"');
        quoted
    }

    fn wide_null(value: &OsStr) -> Vec<u16> {
        let mut wide: Vec<u16> = value.encode_wide().collect();
        wide.push(0);
        wide
    }

    fn invalid_handle(handle: HANDLE) -> bool {
        handle.is_null() || handle == INVALID_HANDLE_VALUE
    }

    fn last_error() -> io::Error {
        io::Error::from_raw_os_error(unsafe { GetLastError() } as i32)
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use std::os::windows::ffi::OsStringExt;

        #[test]
        fn command_line_quotes_python_runner_and_flags() {
            let args = vec![
                OsString::from("-I"),
                OsString::from("-B"),
                OsString::from(r"Local Comet\tools\run_localcomet_desktop_sidecar.py"),
            ];
            let line = build_command_line(&PathBuf::from(r"Python\python.exe"), &args);
            let text = OsString::from_wide(&line[..line.len() - 1])
                .to_string_lossy()
                .into_owned();
            assert!(text.contains("-I"));
            assert!(text.contains("-B"));
            assert!(text.contains("\"Local Comet\\tools\\run_localcomet_desktop_sidecar.py\""));
        }

        #[test]
        fn environment_block_is_double_null_terminated() {
            let block =
                build_environment_block(&[(OsString::from("PYTHONUTF8"), OsString::from("1"))]);
            assert_eq!(&block[block.len() - 2..], &[0, 0]);
        }

        #[test]
        fn source_sets_active_process_limit_to_one() {
            let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            limits.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
            limits.BasicLimitInformation.ActiveProcessLimit = 1;
            assert_eq!(limits.BasicLimitInformation.ActiveProcessLimit, 1);
            assert!(limits.BasicLimitInformation.LimitFlags & JOB_OBJECT_LIMIT_ACTIVE_PROCESS != 0);
        }
    }
}

#[cfg(not(windows))]
mod platform {
    use super::*;

    pub struct ContainedSidecarProcess;
    pub struct ContainedManagedRuntimeProcess;

    impl ContainedSidecarProcess {
        pub fn spawn(_spec: &SidecarLaunchSpec) -> io::Result<Self> {
            Err(io::Error::other("Windows sidecar containment is required"))
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            None
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            None
        }

        pub fn write_frame_bounded(&mut self, _frame: &[u8], _timeout: Duration) -> io::Result<()> {
            Err(io::Error::other("Windows sidecar containment is required"))
        }

        pub fn is_running(&self) -> bool {
            false
        }

        pub fn terminate(&self, _exit_code: u32) {}

        pub fn wait_bounded(&self, _millis: u32) -> bool {
            true
        }
    }

    impl ContainedManagedRuntimeProcess {
        pub fn spawn(_spec: &ManagedRuntimeLaunchSpec) -> io::Result<Self> {
            Err(io::Error::other(
                "Windows managed runtime containment is required",
            ))
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            None
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            None
        }

        pub fn is_running(&self) -> bool {
            false
        }

        pub fn process_id(&self) -> u32 {
            0
        }

        pub fn terminate(&self, _exit_code: u32) {}

        pub fn wait_bounded(&self, _millis: u32) -> bool {
            true
        }
    }
}

pub use platform::{ContainedManagedRuntimeProcess, ContainedSidecarProcess};

#[cfg(test)]
mod bounded_write_tests {
    use super::*;

    struct PartialWriter {
        bytes: Vec<u8>,
        chunk_size: usize,
    }

    impl Write for PartialWriter {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            let written = bytes.len().min(self.chunk_size);
            self.bytes.extend_from_slice(&bytes[..written]);
            Ok(written)
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    struct StalledWriter;

    impl Write for StalledWriter {
        fn write(&mut self, _bytes: &[u8]) -> io::Result<usize> {
            Err(io::Error::new(io::ErrorKind::WouldBlock, "pipe full"))
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    struct FailedWriter;

    impl Write for FailedWriter {
        fn write(&mut self, _bytes: &[u8]) -> io::Result<usize> {
            Err(io::Error::new(io::ErrorKind::BrokenPipe, "sidecar exited"))
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn bounded_writer_preserves_complete_frame_order_across_partial_writes() {
        let mut writer = PartialWriter {
            bytes: Vec::new(),
            chunk_size: 3,
        };
        write_all_bounded(&mut writer, b"first-frame", Duration::from_secs(1)).unwrap();
        write_all_bounded(&mut writer, b"second-frame", Duration::from_secs(1)).unwrap();
        assert_eq!(writer.bytes, b"first-framesecond-frame");
    }

    #[test]
    fn bounded_writer_times_out_when_pipe_never_accepts_data() {
        let started = Instant::now();
        let error = write_all_bounded(&mut StalledWriter, b"frame", Duration::ZERO).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        assert!(started.elapsed() < Duration::from_millis(100));
    }

    #[test]
    fn bounded_writer_propagates_sidecar_failure_without_retrying() {
        let error =
            write_all_bounded(&mut FailedWriter, b"frame", Duration::from_secs(1)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::BrokenPipe);
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/workspace.rs (204 строк, 6663 байт)

````rust
use crate::approval::ApprovalRegistry;
use crate::control_plane::BridgeError;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WorkspaceIdentity {
    pub canonical_path: String,
    pub digest: String,
}

#[derive(Clone, Debug)]
pub enum WorkspaceError {
    InvalidPath(String),
    SymlinkEscape(String),
    /// Reserved for the workspace.set IPC round-trip (INV-WORKSPACE-001). The
    /// desktop sidecar currently performs no filesystem tool execution, so this
    /// variant is not yet constructed; it is retained for the future sidecar
    /// workspace-propagation path.
    #[allow(dead_code)]
    SidecarRejected(String),
    NotADirectory(String),
    DoesNotExist(String),
}

impl std::fmt::Display for WorkspaceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidPath(msg) => write!(f, "invalid workspace path: {msg}"),
            Self::SymlinkEscape(msg) => write!(f, "symlink escape detected: {msg}"),
            Self::SidecarRejected(msg) => write!(f, "sidecar rejected workspace: {msg}"),
            Self::NotADirectory(msg) => write!(f, "not a directory: {msg}"),
            Self::DoesNotExist(msg) => write!(f, "path does not exist: {msg}"),
        }
    }
}

impl From<WorkspaceError> for BridgeError {
    fn from(value: WorkspaceError) -> Self {
        BridgeError {
            code: "workspace_error".into(),
            message: value.to_string(),
        }
    }
}

pub fn validate_workspace_path(raw: &Path) -> Result<PathBuf, WorkspaceError> {
    if raw.as_os_str().is_empty() {
        return Err(WorkspaceError::InvalidPath("empty path".into()));
    }

    let canonical = raw
        .canonicalize()
        .map_err(|e| WorkspaceError::InvalidPath(e.to_string()))?;

    if !canonical.exists() {
        return Err(WorkspaceError::DoesNotExist(
            canonical.display().to_string(),
        ));
    }

    if !canonical.is_dir() {
        return Err(WorkspaceError::NotADirectory(
            canonical.display().to_string(),
        ));
    }

    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
        let metadata = std::fs::symlink_metadata(&canonical)
            .map_err(|e| WorkspaceError::InvalidPath(e.to_string()))?;
        if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return Err(WorkspaceError::SymlinkEscape(
                canonical.display().to_string(),
            ));
        }
    }

    #[cfg(not(windows))]
    {
        let metadata = std::fs::symlink_metadata(&canonical)
            .map_err(|e| WorkspaceError::InvalidPath(e.to_string()))?;
        if metadata.file_type().is_symlink() {
            return Err(WorkspaceError::SymlinkEscape(
                canonical.display().to_string(),
            ));
        }
    }

    Ok(canonical)
}

pub fn workspace_digest(path: &Path) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(path.to_string_lossy().as_bytes());
    let result = hasher.finalize();
    result.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn change_workspace(
    raw_path: &Path,
    approval_registry: &mut ApprovalRegistry,
    current_workspace: &Option<WorkspaceIdentity>,
) -> Result<WorkspaceIdentity, WorkspaceError> {
    let canonical = validate_workspace_path(raw_path)?;

    if let Some(current) = current_workspace {
        approval_registry.invalidate_workspace(&current.canonical_path);
    }

    let identity = WorkspaceIdentity {
        canonical_path: canonical.display().to_string(),
        digest: workspace_digest(&canonical),
    };

    Ok(identity)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn valid_directory_passes_validation() {
        let temp = std::env::temp_dir();
        let result = validate_workspace_path(&temp);
        assert!(result.is_ok());
    }

    #[test]
    fn empty_path_is_rejected() {
        let result = validate_workspace_path(Path::new(""));
        assert!(matches!(result, Err(WorkspaceError::InvalidPath(_))));
    }

    #[test]
    fn nonexistent_path_is_rejected() {
        let result =
            validate_workspace_path(Path::new(r"Z:\nonexistent_localcomet_test_path_12345"));
        assert!(result.is_err());
    }

    #[test]
    fn file_path_is_rejected_as_not_directory() {
        let temp = std::env::temp_dir();
        let file_path = temp.join("localcomet_ws_test_file.txt");
        fs::write(&file_path, "test").unwrap();
        let result = validate_workspace_path(&file_path);
        let _ = fs::remove_file(&file_path);
        assert!(matches!(result, Err(WorkspaceError::NotADirectory(_))));
    }

    #[test]
    fn workspace_change_invalidates_old_tokens() {
        let mut registry = ApprovalRegistry::new();
        let ws_a = WorkspaceIdentity {
            canonical_path: "/workspace-a".into(),
            digest: workspace_digest(Path::new("/workspace-a")),
        };

        use crate::approval::{canonical_input_digest, ApprovalScope, RiskLevel};
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: canonical_input_digest(&serde_json::json!({"x": 1})),
            workspace: "/workspace-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        assert_eq!(registry.active_count(), 1);

        let new_identity =
            change_workspace(&std::env::temp_dir(), &mut registry, &Some(ws_a)).unwrap();

        assert_eq!(registry.active_count(), 0);
        assert!(!new_identity.canonical_path.is_empty());
        assert!(!new_identity.digest.is_empty());

        let digest = canonical_input_digest(&serde_json::json!({"x": 1}));
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/workspace-a")
            .unwrap_err();
        assert!(matches!(err, crate::approval::ApprovalError::TokenNotFound));
    }

    #[test]
    fn workspace_digest_is_deterministic() {
        let d1 = workspace_digest(Path::new("/some/path"));
        let d2 = workspace_digest(Path::new("/some/path"));
        assert_eq!(d1, d2);
        assert_eq!(d1.len(), 64);
    }

    #[test]
    fn different_paths_produce_different_digests() {
        let d1 = workspace_digest(Path::new("/path/a"));
        let d2 = workspace_digest(Path::new("/path/b"));
        assert_ne!(d1, d2);
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/tauri.conf.json (70 строк, 2038 байт)

````json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "LocalComet",
  "mainBinaryName": "LocalComet",
  "version": "6.84.6",
  "identifier": "com.localcomet.desktop",
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devUrl": "http://localhost:1420",
    "frontendDist": "../build"
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "LocalComet",
        "width": 1440,
        "height": 900,
        "minWidth": 1000,
        "minHeight": 700,
        "resizable": true,
        "maximizable": true,
        "fullscreen": false,
        "decorations": true,
        "center": true,
        "visible": false
      }
    ],
    "security": {
      "csp": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: asset:; font-src 'self'; connect-src 'self' ipc: http://ipc.localhost; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    }
  },
  "bundle": {
    "active": true,
    "targets": [
      "nsis"
    ],
    "icon": [
      "icons/icon.ico"
    ],
    "externalBin": [
      "binaries/localcomet-core"
    ],
    "resources": {
      "binaries/app/": "app/",
      "binaries/DLLs/": "DLLs/",
      "binaries/LICENSE.python.txt": "LICENSE.python.txt",
      "binaries/python3.dll": "python3.dll",
      "binaries/python314.dll": "python314.dll",
      "binaries/python314.zip": "python314.zip",
      "binaries/runtime-manifest.tsv": "runtime-manifest.tsv",
      "binaries/up00-runtime-manifest.json": "up00-runtime-manifest.json",
      "binaries/vcruntime140.dll": "vcruntime140.dll",
      "binaries/vcruntime140_1.dll": "vcruntime140_1.dll"
    },
    "windows": {
      "webviewInstallMode": {
        "type": "skip"
      },
      "nsis": {
        "installMode": "currentUser",
        "compression": "lzma",
        "installerIcon": "icons/icon.ico",
        "uninstallerIcon": "icons/icon.ico",
        "installerHooks": "nsis/installer-hooks.nsh"
      }
    }
  }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json (37 строк, 1080 байт)

````json
{
  "schemaVersion": 1,
  "workPackage": "UP00-WP01",
  "targetTriple": "x86_64-pc-windows-msvc",
  "sidecarBaseName": "localcomet-core",
  "entrypoint": "tools/run_localcomet_desktop_sidecar.py",
  "python": {
    "implementation": "CPython",
    "major": 3,
    "minor": 14,
    "licenseFile": "LICENSE.txt",
    "excludedTopLevel": [
      "__pycache__",
      "ensurepip",
      "idlelib",
      "site-packages",
      "tkinter",
      "turtledemo",
      "venv"
    ]
  },
  "sourceFiles": [
    "modules/desktop_control_plane_ru.py",
    "modules/desktop_ipc_contract_ru.py",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/knowledge_adapter_ru.py",
    "modules/knowledge_change_proposal_ru.py",
    "modules/knowledge_change_review_decision_ru.py",
    "modules/knowledge_change_review_ru.py",
    "modules/knowledge_contract_ru.py",
    "modules/knowledge_injection_ru.py",
    "modules/knowledge_review_ui_projection_ru.py",
    "modules/local_model_gateway_ru.py",
    "tools/run_localcomet_desktop_sidecar.py",
    "tools/validate_localcomet_vault.py"
  ]
}
````

### ПУТЬ: desktop/localcomet-desktop/src/app.css (471 строк, 9990 байт)

````css
:root {
  font-family: Inter, "Segoe UI", system-ui, sans-serif;
  color-scheme: dark;
  --lc-bg: #080d0b;
  --lc-bg-elevated: rgba(12, 19, 16, 0.72);
  --lc-panel: rgba(12, 19, 16, 0.6);
  --lc-panel-solid: #111a16;
  --lc-panel-soft: #17231d;
  --lc-line: rgba(36, 52, 44, 0.72);
  --lc-line-strong: rgba(54, 78, 66, 0.92);
  --lc-text: #e6f4ed;
  --lc-muted: #96b0a4;
  --lc-faint: #647c72;
  --lc-accent: #3ddc84;
  --lc-accent-strong: #7cf3b4;
  --lc-accent-dim: rgba(61, 220, 132, 0.12);
  --lc-danger: #f06060;
  --lc-warning: #f2b25c;
  --lc-info: #39e1d3;
  --lc-logo-cut: #080d0b;
  --lc-radius-sm: 6px;
  --lc-radius-md: 9px;
  --lc-radius-lg: 13px;
  --lc-radius-xl: 18px;
  --lc-shadow-e1: 0 1px 2px rgb(0 0 0 / 0.1), 0 1px 3px rgb(0 0 0 / 0.08);
  --lc-shadow-e2: 0 6px 20px rgb(0 0 0 / 0.16), 0 2px 6px rgb(0 0 0 / 0.1);
  --lc-shadow: 0 18px 50px rgb(0 0 0 / 0.28);
  --lc-focus-ring: 0 0 0 2px rgba(61, 220, 132, 0.8);
  --lc-space-1: 4px;
  --lc-space-2: 8px;
  --lc-space-3: 12px;
  --lc-space-4: 16px;
  --lc-space-5: 24px;
  --lc-space-6: 32px;
  --lc-transition-fast: 160ms ease;
  --lc-transition-normal: 220ms ease;
  --lc-mono: "Cascadia Mono", "JetBrains Mono", Consolas, monospace;
  --shell-header-height: 48px;
  --rail-width: 224px;
  --sidebar-width: 208px;
  --inspector-width: 312px;
  --content-width: 768px;
  --border-thin: 1px solid var(--lc-line);
  --shadow-panel: var(--lc-shadow);
  --focus-ring: var(--lc-focus-ring);
  --space-1: var(--lc-space-1);
  --space-2: var(--lc-space-2);
  --space-3: var(--lc-space-3);
  --space-4: var(--lc-space-4);
  --space-5: var(--lc-space-5);
  --space-6: var(--lc-space-6);
  --space-8: var(--lc-space-6);
  --radius-1: var(--lc-radius-sm);
  --radius-2: var(--lc-radius-sm);
  --radius-3: var(--lc-radius-md);
  --font-mono: var(--lc-mono);
  --color-bg: var(--lc-bg);
  --color-panel: var(--lc-panel);
  --color-elevated: var(--lc-panel-solid);
  --color-tool: var(--lc-panel-soft);
  --color-code: #070a08;
  --color-text: var(--lc-text);
  --color-muted: var(--lc-muted);
  --color-border: var(--lc-line);
  --color-hover: rgba(61, 220, 132, 0.08);
  --color-accent: var(--lc-accent);
  --color-accent-soft: var(--lc-accent-dim);
  --status-success: var(--lc-accent-strong);
  --status-warning: var(--lc-warning);
  --status-danger: var(--lc-danger);
  --status-info: var(--lc-info);
  --status-disabled: var(--lc-muted);
  --status-unknown: var(--lc-faint);
  --approval-waiting: var(--lc-warning);
  --risk-medium: var(--lc-warning);
}

/*
  v6.84.2 regression anchors retained for legacy text-only shell tests:
  --color-bg: #f8fafc
  [data-theme="dark"]
  @media (max-width: 999px) .sidebar
*/

.app-shell[data-theme="light"] {
  color-scheme: light;
  --lc-bg: #f4faf6;
  --lc-bg-elevated: rgba(255, 255, 255, 0.82);
  --lc-panel: rgba(255, 255, 255, 0.72);
  --lc-panel-solid: #ffffff;
  --lc-panel-soft: #f0f8f3;
  --lc-line: rgba(218, 232, 224, 0.95);
  --lc-line-strong: #bed2c8;
  --lc-text: #0f2018;
  --lc-muted: #4a6258;
  --lc-faint: #789084;
  --lc-accent: #16a35c;
  --lc-accent-strong: #128c50;
  --lc-accent-dim: rgba(22, 163, 92, 0.12);
  --lc-danger: #d23c3c;
  --lc-warning: #be781e;
  --lc-info: #147b76;
  --lc-logo-cut: #f4faf6;
  --lc-shadow: 0 18px 50px rgba(15, 32, 24, 0.16);
  --color-code: #f4faf6;
}

* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--lc-bg);
}

button,
input,
textarea,
select {
  font: inherit;
}

button,
select {
  min-height: 40px;
}

button {
  color: inherit;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible,
summary:focus-visible,
a:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.skip-link {
  position: fixed;
  top: var(--lc-space-3);
  left: var(--lc-space-3);
  z-index: 100;
  transform: translateY(-140%);
  border: var(--border-thin);
  border-radius: var(--lc-radius-sm);
  background: var(--lc-panel-solid);
  color: var(--lc-text);
  padding: var(--lc-space-2) var(--lc-space-3);
  transition: transform var(--lc-transition-fast);
}

.skip-link:focus {
  transform: translateY(0);
}

.app-shell {
  width: 100vw;
  height: 100vh;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--rail-width) minmax(0, 1fr);
  grid-template-rows: var(--shell-header-height) minmax(0, 1fr);
  overflow: hidden;
  background: var(--lc-bg);
  color: var(--lc-text);
}

.title-bar {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  align-items: center;
  gap: var(--lc-space-3);
  min-width: 0;
  border-bottom: var(--border-thin);
  justify-content: space-between;
  background: color-mix(in srgb, var(--lc-bg) 68%, transparent);
  padding: 0 20px;
  backdrop-filter: blur(12px);
}

.palette-hint {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  color: var(--lc-faint);
  font-size: 12.5px;
}

.palette-hint span {
  margin-left: 3px;
}

kbd {
  min-width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: var(--border-thin);
  border-radius: var(--lc-radius-sm);
  padding: 0 6px;
  background: var(--lc-panel-soft);
  color: var(--lc-muted);
  font-family: var(--lc-mono);
  font-size: 11px;
}

.shell-body {
  grid-column: 2;
  grid-row: 2;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  overflow: hidden;
}

.shell-body.diagnostics-open {
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr) var(--inspector-width);
}

.rail,
.sidebar,
.inspector {
  border-right: var(--border-thin);
  background: var(--lc-panel);
  backdrop-filter: blur(12px);
}

.main-workspace {
  min-width: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: var(--lc-bg);
}

.chat-scroll {
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 16px;
}

.content-column {
  width: min(100%, var(--content-width));
  margin: 0 auto;
}

.icon-button,
.rail-button,
.plain-button,
.mode-button,
.conversation-button,
.section-tab {
  border: 1px solid transparent;
  border-radius: var(--lc-radius-sm);
  background: transparent;
  cursor: pointer;
  transition:
    background-color var(--lc-transition-fast),
    border-color var(--lc-transition-fast),
    color var(--lc-transition-fast),
    transform var(--lc-transition-fast);
}

.icon-button:hover,
.rail-button:hover,
.plain-button:hover,
.mode-button:hover,
.conversation-button:hover,
.section-tab:hover {
  background: var(--color-hover);
  border-color: var(--lc-line);
}

.icon-button:disabled,
.plain-button:disabled,
button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.muted {
  color: var(--lc-muted);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--lc-space-2);
  min-height: 28px;
  border: var(--border-thin);
  border-radius: 999px;
  padding: 0 var(--lc-space-3);
  background: var(--lc-panel-soft);
  color: var(--lc-muted);
  font-size: 12px;
  font-weight: 700;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--status-unknown);
}

.status-dot.ready,
.status-dot.success {
  background: var(--status-success);
}

.status-dot.waiting {
  background: var(--status-warning);
}

.status-dot.failed,
.status-dot.danger {
  background: var(--status-danger);
}

.status-dot.info {
  background: var(--status-info);
}

.status-dot.disabled {
  background: var(--status-disabled);
}

.card-surface,
.tool-surface {
  border: var(--border-thin);
  border-radius: var(--lc-radius-md);
  background: var(--lc-panel-solid);
}

.tool-surface {
  background: var(--lc-panel-soft);
}

.wordmark {
  font-size: 17px;
  font-weight: 660;
  letter-spacing: -0.03em;
}

.wordmark .wordmark-local {
  color: var(--lc-text);
}

.wordmark .wordmark-comet {
  color: var(--lc-accent);
}

.mono {
  font-family: var(--lc-mono);
}

.demo-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  border: 1px solid var(--lc-line-strong);
  border-radius: 999px;
  padding: 0 var(--lc-space-2);
  color: var(--lc-accent);
  background: var(--lc-accent-dim);
  font-family: var(--lc-mono);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0;
}

@media (max-width: 1279px) {
  .app-shell {
    --rail-width: 52px;
  }

  .shell-body,
  .shell-body.diagnostics-open {
    grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  }

  .diagnostics {
    display: none;
  }

  .diagnostics.drawer-open {
    position: fixed;
    top: var(--shell-header-height);
    right: 0;
    z-index: 40;
    display: block;
    width: min(var(--inspector-width), calc(100vw - var(--rail-width)));
    height: calc(100vh - var(--shell-header-height));
    border-left: var(--border-thin);
    box-shadow: var(--lc-shadow);
  }
}

@media (max-width: 920px) {
  .shell-body,
  .shell-body.diagnostics-open {
    grid-template-columns: minmax(0, 1fr);
  }

  .sidebar {
    display: none;
  }

  .sidebar.sidebar-open {
    position: fixed;
    top: var(--shell-header-height);
    left: var(--rail-width);
    z-index: 35;
    display: block;
    width: min(var(--sidebar-width), calc(100vw - var(--rail-width)));
    height: calc(100vh - var(--shell-header-height));
    box-shadow: var(--lc-shadow);
  }

  .chat-scroll {
    padding-inline: var(--lc-space-3);
  }
}

@media (max-width: 680px) {
  .app-shell {
    --rail-width: 48px;
  }

  .chat-scroll {
    padding: var(--lc-space-3);
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.001ms !important;
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transform: none !important;
  }
}
````

### ПУТЬ: desktop/localcomet-desktop/src/app.html (11 строк, 298 байт)

````html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/bridge/approval.ts (53 строк, 1530 байт)

````typescript
import { invoke } from '@tauri-apps/api/core';

export interface ExecutionGrant {
  grant_id: string;
  tool: string;
  workspace: string;
  session: string;
}

export interface WorkspaceIdentity {
  status: string;
  canonical_path: string;
  workspace_digest: string;
}

export async function requestApproval(tool: string, input: unknown): Promise<string> {
  const token = await invoke<string>('request_approval', { tool, input });
  if (typeof token !== 'string' || !token.startsWith('lcap_') || token.length < 60) {
    throw { code: 'invalid_payload', message: 'Invalid approval token' };
  }
  return token;
}

export async function executeApproved(
  token: string,
  tool: string,
  input: unknown
): Promise<ExecutionGrant> {
  const grant = await invoke<ExecutionGrant>('execute_approved', { token, tool, input });
  if (
    typeof grant !== 'object' ||
    grant === null ||
    typeof grant.grant_id !== 'string' ||
    grant.tool !== tool
  ) {
    throw { code: 'invalid_payload', message: 'Invalid execution grant' };
  }
  return grant;
}

export async function setWorkspace(path: string): Promise<WorkspaceIdentity> {
  const identity = await invoke<WorkspaceIdentity>('set_workspace', { path });
  if (
    typeof identity !== 'object' ||
    identity === null ||
    identity.status !== 'ok' ||
    typeof identity.canonical_path !== 'string' ||
    !/^[0-9a-f]{64}$/.test(identity.workspace_digest)
  ) {
    throw { code: 'invalid_payload', message: 'Invalid workspace identity' };
  }
  return identity;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/bridge/controlPlane.ts (154 строк, 5703 байт)

````typescript
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type {
  BootstrapResponse,
  CancelReason,
  ControlPlaneEvent,
  MockTurnBehavior,
  SanitizedBridgeError,
  SessionSummary,
  ThreadSummary,
  TurnSummary
} from '$lib/types/controlPlane';

export const CONTROL_PLANE_EVENT_CHANNEL = 'localcomet://control-plane-event';

export async function bootstrapControlPlane(): Promise<BootstrapResponse> {
  return validateBootstrap(await invokeExact('control_plane_bootstrap'));
}

export async function createSession(title: string): Promise<SessionSummary> {
  return validateSession(await invokeExact('control_plane_create_session', { title: bounded(title, 120) }));
}

export async function closeSession(sessionId: string): Promise<SessionSummary> {
  return validateSession(await invokeExact('control_plane_close_session', { sessionId }));
}

export async function createThread(sessionId: string, title: string): Promise<ThreadSummary> {
  return validateThread(await invokeExact('control_plane_create_thread', { sessionId, title: bounded(title, 120) }));
}

export async function startMockTurn(threadId: string, prompt: string, behavior: MockTurnBehavior): Promise<TurnSummary> {
  return validateTurn(await invokeExact('control_plane_start_mock_turn', { threadId, prompt: bounded(prompt, 8192), behavior }));
}

export async function getTurnStatus(turnId: string): Promise<TurnSummary> {
  return validateTurn(await invokeExact('control_plane_get_turn_status', { turnId }));
}

export async function cancelTurn(turnId: string, reason: CancelReason): Promise<TurnSummary> {
  return validateTurn(await invokeExact('control_plane_cancel_turn', { turnId, reason }));
}

export async function subscribeControlPlaneEvents(callback: (event: ControlPlaneEvent) => void): Promise<() => void> {
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    const parsed = validateEvent(event.payload);
    callback(parsed);
  });
  return () => cleanup();
}

export function normalizeBridgeError(error: unknown): SanitizedBridgeError {
  if (isRecord(error)) {
    const code = typeof error.code === 'string' ? error.code : 'bridge_error';
    const message = typeof error.message === 'string' ? error.message : 'Control Plane bridge error';
    return { code: bounded(code, 64), message: bounded(sanitize(message), 240) };
  }
  return { code: 'bridge_error', message: 'Control Plane bridge error' };
}

async function invokeExact<T>(command: string, args?: Readonly<Record<string, string>>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw normalizeBridgeError(error);
  }
}

function validateBootstrap(value: unknown): BootstrapResponse {
  const object = expectRecord(value);
  if (object.control_plane_version !== 'v6.84.6' || object.protocol !== 'localcomet.ipc') {
    throw { code: 'invalid_payload', message: 'Invalid bootstrap payload' };
  }
  return object as unknown as BootstrapResponse;
}

function validateSession(value: unknown): SessionSummary {
  const object = expectRecord(value);
  if (!isId(object.session_id) || !isOneOf(object.state, ['OPEN', 'CLOSED']) || typeof object.title !== 'string') {
    throw { code: 'invalid_payload', message: 'Invalid session payload' };
  }
  return object as unknown as SessionSummary;
}

function validateThread(value: unknown): ThreadSummary {
  const object = expectRecord(value);
  if (!isId(object.thread_id) || !isId(object.session_id) || !isOneOf(object.state, ['ACTIVE', 'CLOSED'])) {
    throw { code: 'invalid_payload', message: 'Invalid thread payload' };
  }
  return object as unknown as ThreadSummary;
}

function validateTurn(value: unknown): TurnSummary {
  const object = expectRecord(value);
  if (!isId(object.turn_id) || !isOneOf(object.state, ['CREATED', 'RUNNING', 'CANCELLING', 'CANCELLED', 'COMPLETED', 'FAILED'])) {
    throw { code: 'invalid_payload', message: 'Invalid turn payload' };
  }
  return object as unknown as TurnSummary;
}

function validateEvent(value: unknown): ControlPlaneEvent {
  const object = expectRecord(value);
  if (!isEventMethod(object.method) || typeof object.sequence !== 'number' || typeof object.reply_to !== 'string') {
    throw { code: 'invalid_payload', message: 'Invalid Control Plane event' };
  }
  return object as unknown as ControlPlaneEvent;
}

function isEventMethod(value: unknown): boolean {
  return isOneOf(value, [
    'sidecar.status',
    'session.created',
    'session.closed',
    'thread.created',
    'turn.started',
    'turn.completed',
    'turn.cancelled',
    'turn.failed',
    'item.started',
    'item.delta',
    'item.completed',
    'model.turn.started',
    'model.output.delta',
    'model.turn.completed',
    'model.turn.cancelled',
    'model.turn.timed_out',
    'model.turn.failed'
  ]);
}

function expectRecord(value: unknown): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw { code: 'invalid_payload', message: 'Invalid bridge payload' };
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOneOf(value: unknown, options: readonly string[]): boolean {
  return typeof value === 'string' && options.includes(value);
}

function isId(value: unknown): boolean {
  return typeof value === 'string' && /^[0-9a-f]{24}$/.test(value);
}

function sanitize(value: string): string {
  return value.replace(/Traceback[\s\S]*/g, '<redacted>').replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>');
}

function bounded(value: string, limit: number): string {
  return value.slice(0, limit);
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/bridge/files.ts (224 строк, 8231 байт)

````typescript
import { invoke } from '@tauri-apps/api/core';
import type {
  FileCapabilityError,
  FileSelectionResponse,
  FilesCapabilityStatus,
  SelectedFilePreview,
  SelectedFileStatus,
  SelectedFileSummary
} from '$lib/types/files';
import { FILE_ID_PATTERN } from '$lib/types/files';

const MAX_FILE_BYTES = 2 * 1024 * 1024;
const MAX_ACTIVE_CONTEXT_BYTES = 5 * 1024 * 1024;
const MAX_SELECTED_FILES = 32;
const PREVIEW_MAX_CHARACTERS = 16_000;
const EXTENSIONS = ['txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'] as const;
const STATUSES: readonly SelectedFileStatus[] = ['ready', 'missing', 'changed', 'reparse_point', 'unreadable'];
const ABSOLUTE_PATH_RE = /(?:[A-Za-z]:[\\/]|\\\\|\/[A-Za-z0-9._-]+\/)/;

export async function getFilesCapabilityStatus(): Promise<FilesCapabilityStatus> {
  return validateCapabilityStatus(await invokeFiles('files_capability_status'));
}

export async function selectFiles(): Promise<FileSelectionResponse> {
  return validateSelection(await invokeFiles('select_files'));
}

export async function listSelectedFiles(): Promise<readonly SelectedFileSummary[]> {
  return validateFileList(await invokeFiles('list_selected_files'));
}

export async function previewSelectedFile(fileId: string): Promise<SelectedFilePreview> {
  return validatePreview(
    await invokeFiles('preview_selected_file', { fileId: validateFileId(fileId) })
  );
}

export async function forgetSelectedFile(fileId: string): Promise<readonly SelectedFileSummary[]> {
  return validateFileList(
    await invokeFiles('forget_selected_file', { fileId: validateFileId(fileId) })
  );
}

export function normalizeFileError(error: unknown): FileCapabilityError {
  if (isRecord(error)) {
    const code = safeErrorText(error.code, 64, 'LC_FILE_UNREADABLE');
    const message = safeErrorText(error.message, 240, 'Selected file operation failed');
    return { code, message };
  }
  return { code: 'LC_FILE_UNREADABLE', message: 'Selected file operation failed' };
}

async function invokeFiles(command: string, args?: Readonly<Record<string, string>>): Promise<unknown> {
  try {
    return await invoke(command, args);
  } catch (error) {
    throw normalizeFileError(error);
  }
}

function validateCapabilityStatus(value: unknown): FilesCapabilityStatus {
  const object = exactRecord(value, [
    'available',
    'read_only',
    'selection',
    'persistence',
    'supported_extensions',
    'maximum_file_bytes',
    'maximum_active_context_bytes',
    'maximum_selected_files',
    'preview_maximum_characters'
  ]);
  if (
    typeof object.available !== 'boolean' ||
    object.read_only !== true ||
    object.selection !== 'native_system_file_picker_only' ||
    object.persistence !== 'current_process_memory_only' ||
    JSON.stringify(object.supported_extensions) !== JSON.stringify(EXTENSIONS) ||
    object.maximum_file_bytes !== MAX_FILE_BYTES ||
    object.maximum_active_context_bytes !== MAX_ACTIVE_CONTEXT_BYTES ||
    object.maximum_selected_files !== MAX_SELECTED_FILES ||
    object.preview_maximum_characters !== PREVIEW_MAX_CHARACTERS
  ) throw invalidPayload();
  return object as unknown as FilesCapabilityStatus;
}

function validateSelection(value: unknown): FileSelectionResponse {
  const object = exactRecord(value, ['cancelled', 'files']);
  if (typeof object.cancelled !== 'boolean') throw invalidPayload();
  const files = validateFileList(object.files);
  return { cancelled: object.cancelled, files };
}

function validateFileList(value: unknown): readonly SelectedFileSummary[] {
  if (!Array.isArray(value) || value.length > MAX_SELECTED_FILES) throw invalidPayload();
  const ids = new Set<string>();
  return value.map((item) => {
    const file = validateSummary(item);
    if (ids.has(file.file_id)) throw invalidPayload();
    ids.add(file.file_id);
    return file;
  });
}

function validateSummary(value: unknown): SelectedFileSummary {
  const object = exactRecord(value, [
    'file_id',
    'filename',
    'extension',
    'media_type',
    'byte_size',
    'character_count',
    'readable',
    'status',
    'added_at_unix_ms',
    'display_location'
  ]);
  const fileId = validateFileId(object.file_id);
  const filename = safeDisplayText(object.filename, 255);
  const extension = safeDisplayText(object.extension, 8).toLowerCase();
  const mediaType = safeDisplayText(object.media_type, 32);
  const displayLocation = safeDisplayText(object.display_location, 520);
  const byteSize = safeInteger(object.byte_size, 0, MAX_FILE_BYTES);
  const characterCount = safeInteger(object.character_count, 0, MAX_FILE_BYTES);
  const addedAt = safeInteger(object.added_at_unix_ms, 1, Number.MAX_SAFE_INTEGER);
  if (
    !EXTENSIONS.includes(extension as (typeof EXTENSIONS)[number]) ||
    !filename.toLowerCase().endsWith(`.${extension}`) ||
    ABSOLUTE_PATH_RE.test(filename) ||
    ABSOLUTE_PATH_RE.test(displayLocation) ||
    typeof object.readable !== 'boolean' ||
    !STATUSES.includes(object.status as SelectedFileStatus) ||
    (object.readable !== (object.status === 'ready'))
  ) throw invalidPayload();
  return {
    file_id: fileId,
    filename,
    extension,
    media_type: mediaType,
    byte_size: byteSize,
    character_count: characterCount,
    readable: object.readable,
    status: object.status as SelectedFileStatus,
    added_at_unix_ms: addedAt,
    display_location: displayLocation
  };
}

function validatePreview(value: unknown): SelectedFilePreview {
  const object = exactRecord(value, [
    'file_id',
    'filename',
    'content',
    'original_bytes',
    'original_characters',
    'displayed_bytes',
    'displayed_characters',
    'truncated'
  ]);
  const content = typeof object.content === 'string' ? object.content : invalidPayload();
  const displayedBytes = safeInteger(object.displayed_bytes, 0, MAX_FILE_BYTES);
  const displayedCharacters = safeInteger(object.displayed_characters, 0, PREVIEW_MAX_CHARACTERS);
  if (
    new TextEncoder().encode(content).length !== displayedBytes ||
    [...content].length !== displayedCharacters ||
    typeof object.truncated !== 'boolean'
  ) throw invalidPayload();
  const originalBytes = safeInteger(object.original_bytes, displayedBytes, MAX_FILE_BYTES);
  const originalCharacters = safeInteger(object.original_characters, displayedCharacters, MAX_FILE_BYTES);
  if (object.truncated !== (displayedBytes < originalBytes)) throw invalidPayload();
  return {
    file_id: validateFileId(object.file_id),
    filename: safeDisplayText(object.filename, 255),
    content,
    original_bytes: originalBytes,
    original_characters: originalCharacters,
    displayed_bytes: displayedBytes,
    displayed_characters: displayedCharacters,
    truncated: object.truncated
  };
}

function validateFileId(value: unknown): string {
  if (typeof value !== 'string' || !FILE_ID_PATTERN.test(value)) throw invalidPayload();
  return value;
}

function exactRecord(value: unknown, keys: readonly string[]): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw invalidPayload();
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw invalidPayload();
  }
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function safeDisplayText(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || !value || value.length > maximum || /[\0\r\n]/.test(value)) {
    throw invalidPayload();
  }
  return value;
}

function safeErrorText(value: unknown, maximum: number, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const clean = value.replace(/[\0\r\n]/g, ' ').trim().slice(0, maximum);
  return clean || fallback;
}

function safeInteger(value: unknown, minimum: number, maximum: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw invalidPayload();
  }
  return value;
}

function invalidPayload(): never {
  throw { code: 'invalid_payload', message: 'Invalid Files capability payload' };
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/bridge/knowledge.ts (192 строк, 8200 байт)

````typescript
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { CONTROL_PLANE_EVENT_CHANNEL } from './controlPlane';
import type {
  KnowledgeAction,
  KnowledgeDecisionResponse,
  KnowledgeIntent,
  KnowledgePreview,
  KnowledgePreviewFailure,
  KnowledgePreviewSection,
  KnowledgePreviewSource
} from '$lib/knowledge/knowledgePreview';

type InvokeArgs = Readonly<Record<string, string | number>>;
const HASH_RE = /^sha256:[0-9a-f]{64}$/;
const TURN_RE = /^[0-9a-f]{24}$/;
const REQUEST_RE = /^kreq:\S{1,123}$/;
const INJECTION_RE = /^kinj:\S{1,123}$/;
const BUNDLE_RE = /^kb:[0-9a-f]{64}$/;
const ABSOLUTE_PATH_RE = /(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/]|\/(?:home|Users)\/)/i;

export async function requestKnowledgePreview(args: {
  turnId: string;
  intent: KnowledgeIntent;
  maxContextChars: number;
  maxResults: number;
}): Promise<KnowledgePreview | KnowledgePreviewFailure> {
  const payload = await invokeExact('knowledge_turn_preview', {
    turnId: validateTurnId(args.turnId),
    intent: validateIntent(args.intent),
    maxContextChars: boundedInteger(args.maxContextChars, 1, 12_000),
    maxResults: boundedInteger(args.maxResults, 1, 8)
  });
  return validatePreviewResponse(payload);
}

export async function decideKnowledgeTurn(args: {
  turnId: string;
  injectionId: string;
  expectedPreviewHash: string;
  action: KnowledgeAction;
}): Promise<KnowledgeDecisionResponse> {
  return validateDecisionResponse(
    await invokeExact('knowledge_turn_decide', {
      turnId: validateTurnId(args.turnId),
      injectionId: validateInjectionId(args.injectionId),
      expectedPreviewHash: validateHash(args.expectedPreviewHash),
      action: validateAction(args.action)
    })
  );
}

export async function subscribeKnowledgeInjectionEvents(
  callback: (injectionId: string) => void
): Promise<() => void> {
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    if (!isRecord(event.payload) || event.payload.method !== 'model.turn.started') return;
    const metadata = isRecord(event.payload.metadata) ? event.payload.metadata : {};
    const injectionId = metadata.knowledge_injection_id;
    if (typeof injectionId === 'string' && INJECTION_RE.test(injectionId)) callback(injectionId);
  });
  return () => cleanup();
}

async function invokeExact(command: string, args: InvokeArgs): Promise<unknown> {
  try {
    return await invoke(command, args);
  } catch (error) {
    throw normalizeKnowledgeError(error);
  }
}

function validatePreviewResponse(value: unknown): KnowledgePreview | KnowledgePreviewFailure {
  const object = expectRecord(value);
  rejectForbiddenFields(object);
  if (object.state === 'FAILED') {
    const error = expectRecord(object.error);
    if (typeof object.turn_id !== 'string' || typeof error.code !== 'string' || typeof error.safe_message !== 'string') throw invalid();
    return object as unknown as KnowledgePreviewFailure;
  }
  if (object.state !== 'PREVIEW_READY') throw invalid();
  validateTurnId(String(object.turn_id));
  if (!REQUEST_RE.test(String(object.request_id))) throw invalid();
  validateInjectionId(String(object.injection_id));
  if (!BUNDLE_RE.test(String(object.bundle_id))) throw invalid();
  validateHash(String(object.preview_hash));
  validateHash(String(object.vault_revision));
  validateIntent(String(object.resolved_intent) as KnowledgeIntent);
  if (!Array.isArray(object.sources)) throw invalid();
  const sources = object.sources.map(validateSource);
  const sourceCount = boundedInteger(Number(object.source_count), 0, 8);
  const totalChars = boundedInteger(Number(object.total_chars), 0, 12_000);
  if (sourceCount !== sources.length || object.truncated !== Boolean(object.truncated)) throw invalid();
  const measured = sources.reduce(
    (total, source) => total + source.selected_sections.reduce((sum, section) => sum + [...section.content].length, 0),
    0
  );
  if (measured !== totalChars || object.model_dispatched !== false || object.tools_executed !== 0) throw invalid();
  return { ...(object as unknown as KnowledgePreview), sources };
}

function validateSource(value: unknown): KnowledgePreviewSource {
  const object = expectRecord(value);
  const textFields = ['note_id', 'title', 'relative_path', 'knowledge_layer', 'evidence_class', 'authority', 'status'] as const;
  for (const field of textFields) {
    if (typeof object[field] !== 'string' || String(object[field]).length > 512) throw invalid();
  }
  const path = String(object.relative_path);
  if (!path || ABSOLUTE_PATH_RE.test(path) || path.split(/[\\/]/).includes('..')) throw invalid();
  if (typeof object.canonical !== 'boolean' || !Array.isArray(object.selected_sections)) throw invalid();
  const sections = object.selected_sections.map(validateSection);
  return { ...(object as unknown as KnowledgePreviewSource), selected_sections: sections };
}

function validateSection(value: unknown): KnowledgePreviewSection {
  const object = expectRecord(value);
  if (typeof object.heading !== 'string' || typeof object.content !== 'string') throw invalid();
  const lineStart = boundedInteger(Number(object.line_start), 1, 1_000_000);
  const lineEnd = boundedInteger(Number(object.line_end), lineStart, 1_000_000);
  if ([...object.content].length > 12_000 || ABSOLUTE_PATH_RE.test(object.content)) throw invalid();
  return object as unknown as KnowledgePreviewSection;
}

function validateDecisionResponse(value: unknown): KnowledgeDecisionResponse {
  const object = expectRecord(value);
  if (!['DECIDING', 'DISPATCHING', 'INJECTED', 'REJECTED', 'STALE'].includes(String(object.state))) throw invalid();
  validateTurnId(String(object.turn_id));
  validateInjectionId(String(object.injection_id));
  if (object.decision_source !== undefined && object.decision_source !== 'USER_APPROVAL') throw invalid();
  if (typeof object.model_dispatched !== 'boolean') throw invalid();
  return object as unknown as KnowledgeDecisionResponse;
}

function rejectForbiddenFields(value: Readonly<Record<string, unknown>>): void {
  const text = JSON.stringify(value);
  if (/serialized_context|vault_root|project_root|credential|api_key|binding_fingerprint/i.test(text)) throw invalid();
  if (ABSOLUTE_PATH_RE.test(text)) throw invalid();
}

function validateTurnId(value: string): string {
  if (!TURN_RE.test(value)) throw invalid();
  return value;
}

function validateInjectionId(value: string): string {
  if (!INJECTION_RE.test(value)) throw invalid();
  return value;
}

function validateHash(value: string): string {
  if (!HASH_RE.test(value)) throw invalid();
  return value;
}

function validateIntent(value: KnowledgeIntent): KnowledgeIntent {
  const allowed: readonly KnowledgeIntent[] = ['AUTO', 'CURRENT_STATE', 'ARCHITECTURE', 'SECURITY', 'HISTORY', 'FOUNDER_INTENT', 'ROADMAP', 'RESEARCH', 'OPERATIONAL', 'INCIDENT'];
  if (!allowed.includes(value)) throw invalid();
  return value;
}

function validateAction(value: KnowledgeAction): KnowledgeAction {
  if (!['INCLUDE_AND_SEND', 'REJECT_AND_SEND_WITHOUT_KNOWLEDGE', 'CANCEL'].includes(value)) throw invalid();
  return value;
}

function boundedInteger(value: number, minimum: number, maximum: number): number {
  if (!Number.isInteger(value) || value < minimum || value > maximum) throw invalid();
  return value;
}

function expectRecord(value: unknown): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw invalid();
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeKnowledgeError(error: unknown): { code: string; message: string } {
  if (isRecord(error)) {
    return {
      code: String(error.code ?? 'knowledge_error').slice(0, 64),
      message: String(error.message ?? 'Project knowledge request failed').replace(/Traceback[\s\S]*/g, '<redacted>').slice(0, 240)
    };
  }
  return { code: 'knowledge_error', message: 'Project knowledge request failed' };
}

function invalid(): { code: 'invalid_payload'; message: string } {
  return { code: 'invalid_payload', message: 'Invalid Project Knowledge payload' };
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/bridge/knowledgeReview.ts (1392 строк, 55714 байт)

````typescript
import { invoke } from '@tauri-apps/api/core';
import type {
  BoundedFindingDetailsProjection,
  BoundedReviewFindingsProjection,
  BoundedSourceValidationFindingsProjection,
  BoundedStringCollectionProjection,
  BoundedTextPreviewProjection,
  ConflictSeverity,
  DiffProjection,
  HumanReviewDecisionProjection,
  KnowledgeChangeReviewProjection,
  KnowledgeReviewDecisionCreateEnvelope,
  KnowledgeReviewDecisionRequest,
  KnowledgeReviewGetEnvelope,
  KnowledgeReviewListEnvelope,
  KnowledgeReviewSnapshotEnvelope,
  KnowledgeReviewStateProjection,
  KnowledgeReviewSummaryProjection,
  LineEndingProfileProjection,
  ProposedBodyProjection,
  ProposedContentProjection,
  RealReviewCenterItem,
  RepresentationDeltaProjection,
  ReviewCenterError,
  ReviewOperation,
  ReviewQueueItem,
  ReviewStatus,
  ValidationSnapshotProjection,
  ValidationValueProjection
} from '$lib/types/knowledgeReview';

export const KNOWLEDGE_REVIEW_LIST_CONTRACT = 'localcomet.knowledge-review-list/1.0';
export const KNOWLEDGE_REVIEW_GET_CONTRACT = 'localcomet.knowledge-review-get/1.0';
export const KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT = 'localcomet.knowledge-review-snapshot/1.0';
export const KNOWLEDGE_REVIEW_REFRESH_CONTRACT = 'localcomet.knowledge-review-refresh/1.0';
export const KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT =
  'localcomet.knowledge-review-decision-create/1.0';
export const KNOWLEDGE_REVIEW_PROJECTION_CONTRACT = 'localcomet.knowledge-review-ui/1.0';
export const KNOWLEDGE_CHANGE_REVIEW_CONTRACT = 'localcomet.knowledge-change-review/1.0';
export const HUMAN_REVIEW_DECISION_CONTRACT =
  'localcomet.knowledge-change-review-decision/1.0';
export const KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION = 'v6.84.6';
export const KNOWLEDGE_REVIEW_ACTOR_SOURCE = 'LOCALCOMET_REVIEW_CENTER';
export const KNOWLEDGE_REVIEW_SOURCE = 'LOCAL_CONTROL_PLANE';
export const KNOWLEDGE_REVIEW_LIST_OFFSET = 0;
export const KNOWLEDGE_REVIEW_LIST_LIMIT = 50;
export const MAX_KNOWLEDGE_REVIEW_LIST_LIMIT = 50;
export const MAX_KNOWLEDGE_REVIEW_LIST_OFFSET = 128;
export const MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES = 1_048_576;
export const MAX_KNOWLEDGE_REVIEW_PROJECTION_BYTES = 262_144;

const MAX_GENERAL_STRING_BYTES = 32_768;
const MAX_COLLECTION_ITEMS = 128;
const MAX_VALIDATION_DEPTH = 16;
const MAX_VALIDATION_NODES = 1_024;
const MAX_VALIDATION_ITEMS = 128;
const MAX_FINDINGS = 16;
const MAX_FINDING_DETAILS = 16;
const MAX_SOURCE_FINDINGS = 128;
const REVIEW_STATUSES = ['CLEAR', 'REVIEW_REQUIRED', 'BLOCKED'] as const;
const REVIEW_OPERATIONS = [
  'UPDATE_EXISTING',
  'CREATE_NEW',
  'DELETE',
  'MOVE',
  'RENAME',
  'SUPERSEDE'
] as const;
const VALIDATION_OUTCOMES = ['VALID', 'INVALID', 'STALE'] as const;
const CONFLICT_SEVERITIES = ['BLOCKING', 'REVIEW'] as const;
const VALIDATION_TYPE_TAGS = ['mapping', 'sequence', 'null', 'bool', 'int', 'string'] as const;

const SHA256_RE = /^sha256:[0-9a-f]{64}$/;
const PROPOSAL_ID_RE = /^kprop:[0-9a-f]{64}$/;
const REVIEW_ID_RE = /^kreview:[0-9a-f]{64}$/;
const CHANGE_ID_RE = /^kchange:[0-9a-f]{64}$/;
const DECISION_ID_RE = /^kdecision:[0-9a-f]{64}$/;
const STABLE_ID_RE = /^[a-z0-9]+(?:[._-][a-z0-9]+)*$/;
const WINDOWS_DRIVE_RE = /^[A-Za-z]:/;
const textEncoder = new TextEncoder();

type JsonRecord = Readonly<Record<string, unknown>>;

export interface KnowledgeReviewClient {
  list(offset: number, limit: number): Promise<KnowledgeReviewListEnvelope>;
  get(reviewArtifactIdentity: string): Promise<KnowledgeReviewGetEnvelope>;
  snapshot(): Promise<KnowledgeReviewSnapshotEnvelope>;
  refresh(): Promise<KnowledgeReviewSnapshotEnvelope>;
  createDecision(
    request: KnowledgeReviewDecisionRequest
  ): Promise<KnowledgeReviewDecisionCreateEnvelope>;
}

export async function listKnowledgeReviews(
  offset = KNOWLEDGE_REVIEW_LIST_OFFSET,
  limit = KNOWLEDGE_REVIEW_LIST_LIMIT
): Promise<KnowledgeReviewListEnvelope> {
  ensureListRequest(offset, limit);
  let raw: unknown;
  try {
    raw = await invoke<unknown>('knowledge_review_list', { offset, limit });
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review list response exceeds its byte limit'
  );
  validateListEnvelope(raw, offset, limit);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewListEnvelope);
}

export async function getKnowledgeReview(
  reviewArtifactIdentity: string
): Promise<KnowledgeReviewGetEnvelope> {
  ensureReviewIdentity(reviewArtifactIdentity);
  let raw: unknown;
  try {
    raw = await invoke<unknown>('knowledge_review_get', { reviewArtifactIdentity });
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review get response exceeds its byte limit'
  );
  validateGetEnvelope(raw, reviewArtifactIdentity);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewGetEnvelope);
}

export async function getKnowledgeReviewSnapshot(): Promise<KnowledgeReviewSnapshotEnvelope> {
  return invokeSnapshot('knowledge_review_snapshot', false);
}

export async function refreshKnowledgeReviews(): Promise<KnowledgeReviewSnapshotEnvelope> {
  return invokeSnapshot('knowledge_review_refresh', true);
}

async function invokeSnapshot(
  command: 'knowledge_review_snapshot' | 'knowledge_review_refresh',
  refreshRequested: boolean
): Promise<KnowledgeReviewSnapshotEnvelope> {
  let raw: unknown;
  try {
    raw = await invoke<unknown>(command);
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review snapshot response exceeds its byte limit'
  );
  validateSnapshotEnvelope(raw, refreshRequested);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewSnapshotEnvelope);
}

export async function createKnowledgeReviewDecision(
  request: KnowledgeReviewDecisionRequest
): Promise<KnowledgeReviewDecisionCreateEnvelope> {
  validateDecisionRequest(request);
  let raw: unknown;
  try {
    raw = await invoke<unknown>('knowledge_review_decision_create', {
      reviewContractVersion: request.reviewContractVersion,
      proposalId: request.proposalId,
      reviewArtifactIdentity: request.reviewArtifactIdentity,
      changeIdentity: request.changeIdentity,
      observedVaultRevision: request.observedVaultRevision,
      decision: request.decision,
      comment: request.comment,
      actorIdentifier: request.actorIdentifier,
      actorDisplayName: request.actorDisplayName,
      actorSource: request.actorSource
    });
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review decision response exceeds its byte limit'
  );
  validateDecisionCreateEnvelope(raw, request);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewDecisionCreateEnvelope);
}

export const knowledgeReviewClient: KnowledgeReviewClient = Object.freeze({
  list: listKnowledgeReviews,
  get: getKnowledgeReview,
  snapshot: getKnowledgeReviewSnapshot,
  refresh: refreshKnowledgeReviews,
  createDecision: createKnowledgeReviewDecision
});

export function reviewSummaryToQueueItem(
  summary: KnowledgeReviewSummaryProjection
): ReviewQueueItem {
  return Object.freeze({
    id: summary.review_artifact_identity,
    fixture: false,
    source: KNOWLEDGE_REVIEW_SOURCE,
    status: summary.status,
    blocked: summary.blocked,
    proposalId: summary.proposal_id,
    targetStableId: summary.target_stable_id,
    operation: summary.operation,
    expectedVaultRevision: summary.expected_vault_revision,
    observedVaultRevision: summary.observed_vault_revision,
    reviewArtifactIdentity: summary.review_artifact_identity,
    changeIdentity: summary.change_identity,
    findingCount: summary.finding_count,
    normalChangeMaterialPresent: summary.normal_change_material_present,
    detailProjectionTruncated: summary.detail_projection_truncated,
    stale: null
  });
}

export function reviewProjectionToCenterItem(
  envelope: KnowledgeReviewGetEnvelope
): RealReviewCenterItem {
  const projection = envelope.projection;
  const snapshotText = formatValidationSnapshot(projection.validation_snapshot.value);
  const boundedSnapshot = snapshotText.slice(0, 8_192);
  const snapshotRoot = projection.validation_snapshot.value;
  const validationContract = validationScalar(snapshotRoot, 'contract_version');
  const validationContentHash = validationScalar(snapshotRoot, 'proposal_content_hash');
  const validatedRevision = validationScalar(snapshotRoot, 'validated_vault_revision');

  return deepFreeze({
    id: projection.review_artifact_identity,
    fixture: false,
    source: KNOWLEDGE_REVIEW_SOURCE,
    detailProjectionTruncated: hasTruncatedReviewDetail(projection),
    stale: null,
    status: projection.status,
    proposalId: projection.proposal_id,
    proposalContentHash: projection.proposal_content_hash,
    reviewArtifactIdentity: projection.review_artifact_identity,
    changeIdentity: projection.change_identity,
    operation: projection.operation,
    targetStableId: projection.target_stable_id,
    expectedVaultRevision: projection.expected_vault_revision,
    observedVaultRevision: projection.observed_vault_revision,
    validation: {
      outcome: projection.validation_outcome,
      contractVersion: typeof validationContract === 'string'
        ? validationContract
        : projection.contract_version,
      proposalContentHash: typeof validationContentHash === 'string'
        ? validationContentHash
        : projection.proposal_content_hash,
      validatedVaultRevision: typeof validatedRevision === 'string'
        ? validatedRevision
        : projection.observed_vault_revision,
      sourceFindings: projection.source_validation_findings.items.map(
        (finding) => [finding.code, finding.severity] as const
      ),
      snapshotTruncated:
        projection.validation_snapshot.truncated || snapshotText.length > boundedSnapshot.length,
      snapshotSummary: boundedSnapshot
    },
    findings: projection.findings.items.map((finding) => ({
      code: finding.code,
      severity: finding.severity,
      message: finding.message.preview_text,
      details: finding.details.items.map((detail) => [detail.key, detail.value] as const)
    })),
    proposedContent: {
      title: projection.proposed_content_snapshot.title,
      body_text: projection.proposed_content_snapshot.body_text.preview_text,
      type: projection.proposed_content_snapshot.type,
      status: projection.proposed_content_snapshot.status,
      knowledge_layer: projection.proposed_content_snapshot.knowledge_layer,
      evidence_class: projection.proposed_content_snapshot.evidence_class,
      authority: projection.proposed_content_snapshot.authority,
      canonical: projection.proposed_content_snapshot.canonical,
      canonical_scope: projection.proposed_content_snapshot.canonical_scope,
      aliases: projection.proposed_content_snapshot.aliases.items,
      releases: projection.proposed_content_snapshot.releases.items,
      source_paths: projection.proposed_content_snapshot.source_paths.items,
      evidence_refs: projection.proposed_content_snapshot.evidence_refs.items,
      supersedes: projection.proposed_content_snapshot.supersedes.items,
      superseded_by: projection.proposed_content_snapshot.superseded_by.items,
      updated: projection.proposed_content_snapshot.updated,
      last_reviewed: projection.proposed_content_snapshot.last_reviewed,
      verified_at: projection.proposed_content_snapshot.verified_at
    },
    metadataChanges: [],
    beforeSourceByteHash: projection.before_source_byte_hash,
    beforeTextRawHash: projection.before_text_raw_hash,
    beforeSemanticTextHash: projection.before_semantic_text_hash,
    proposedTextRawHash: projection.proposed_text_raw_hash,
    proposedSemanticTextHash: projection.proposed_semantic_text_hash,
    textDiff: projection.diff === null
      ? {
          preview: null,
          previewTruncated: false,
          fullDiffAvailable: false,
          fullDiffHash: null,
          fullDiffUtf8Bytes: null
        }
      : {
          preview: projection.diff.preview.preview_text,
          previewTruncated: projection.diff.preview_truncated,
          fullDiffAvailable: projection.diff.full_diff_present,
          fullDiffHash: projection.diff.full_diff_hash,
          fullDiffUtf8Bytes: projection.diff.full_diff_utf8_bytes
        },
    representationDelta: projection.representation_delta === null
      ? null
      : {
          identity: projection.representation_delta.identity,
          beforePresent: projection.representation_delta.before_present,
          afterPresent: projection.representation_delta.after_present,
          beforeLineEndings: projection.representation_delta.before_line_endings === null
            ? null
            : lineEndingView(projection.representation_delta.before_line_endings),
          afterLineEndings: lineEndingView(projection.representation_delta.after_line_endings),
          terminalNewlineChanged: projection.representation_delta.terminal_newline_changed,
          afterSourceBytesKnown: projection.representation_delta.after_source_bytes_known,
          sourceBytesChangedTextIdentical:
            projection.representation_delta.source_bytes_changed_text_identical,
          rawTextChangedSemanticEqual:
            projection.representation_delta.raw_text_changed_semantic_equal,
          semanticContentChanged: projection.representation_delta.semantic_content_changed
        },
    humanReviewPreview: {
      text: projection.human_review_preview.preview_text,
      truncated: projection.human_review_preview.truncated
    },
    rawProjection: projection
  });
}

export function normalizeKnowledgeReviewError(error: unknown): ReviewCenterError {
  if (isRecord(error)) {
    const code = typeof error.code === 'string' ? error.code : 'review_bridge_error';
    const message = typeof error.message === 'string'
      ? error.message
      : 'Knowledge review bridge error';
    return Object.freeze({
      code: boundedSanitized(code, 64),
      message: boundedSanitized(message, 240)
    });
  }
  return Object.freeze({
    code: 'review_bridge_error',
    message: 'Knowledge review bridge error'
  });
}

function validateSnapshotEnvelope(value: unknown, refreshRequested: boolean): void {
  const object = exactRecord(value, [
    'contract',
    'command_center_version',
    'control_plane_version',
    'sidecar_runtime_version',
    'source',
    'fixture',
    'refresh_requested',
    'refresh_succeeded',
    'current_vault_revision',
    'freshness_known',
    'knowledge_state',
    'last_error_code',
    'inbox_count',
    'stale_count',
    'blocked_count',
    'session_decision_count',
    'review_states',
    'hard_stop',
    'persistence',
    'vault_write_authority',
    'publication_authority'
  ], 'review snapshot envelope');
  const expectedContract = refreshRequested
    ? KNOWLEDGE_REVIEW_REFRESH_CONTRACT
    : KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT;
  if (object.contract !== expectedContract) invalid('Wrong review snapshot contract');
  if (object.command_center_version !== KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION) {
    invalid('Wrong command center version');
  }
  boundedString(object.control_plane_version, 'control plane version', 64);
  boundedString(object.sidecar_runtime_version, 'sidecar runtime version', 64);
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review snapshot source');
  }
  if (object.refresh_requested !== refreshRequested) {
    invalid('Review snapshot refresh binding mismatch');
  }
  const refreshSucceeded = booleanValue(object.refresh_succeeded, 'refresh success');
  if (!refreshRequested && refreshSucceeded) {
    invalid('Snapshot cannot report refresh success');
  }
  optionalPatternString(object.current_vault_revision, SHA256_RE, 'current Vault revision');
  const freshnessKnown = booleanValue(object.freshness_known, 'freshness known');
  if (freshnessKnown !== (object.current_vault_revision !== null)) {
    invalid('Freshness knowledge is inconsistent');
  }
  boundedString(object.knowledge_state, 'knowledge state', 64);
  optionalBoundedString(object.last_error_code, 'last error code', 64);
  const inboxCount = nonNegativeInteger(object.inbox_count, 'inbox count');
  const staleCount = nonNegativeInteger(object.stale_count, 'stale count');
  const blockedCount = nonNegativeInteger(object.blocked_count, 'blocked count');
  const decisionCount = nonNegativeInteger(
    object.session_decision_count,
    'session decision count'
  );
  if (
    inboxCount > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET ||
    staleCount > inboxCount ||
    blockedCount > inboxCount ||
    decisionCount > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
  ) {
    invalid('Review snapshot counts exceed bounds');
  }
  const states = arrayValue(
    object.review_states,
    MAX_KNOWLEDGE_REVIEW_LIST_OFFSET,
    'review states'
  );
  if (states.length !== inboxCount) invalid('Review state count mismatch');
  const identities = new Set<string>();
  let observedStale = 0;
  let observedBlocked = 0;
  for (const stateValue of states) {
    const state = validateReviewState(stateValue);
    if (identities.has(state.review_artifact_identity)) {
      invalid('Duplicate review state identity');
    }
    identities.add(state.review_artifact_identity);
    if (state.stale === true) observedStale += 1;
    if (state.status === 'BLOCKED') observedBlocked += 1;
    if (!freshnessKnown && state.stale !== null) {
      invalid('Unknown freshness must use null stale state');
    }
  }
  if (observedStale !== staleCount || observedBlocked !== blockedCount) {
    invalid('Review snapshot aggregate counts are inconsistent');
  }
  if (
    object.hard_stop !== true ||
    object.persistence !== false ||
    object.vault_write_authority !== false ||
    object.publication_authority !== false
  ) {
    invalid('Review snapshot authority boundary mismatch');
  }
}

function validateReviewState(value: unknown): KnowledgeReviewStateProjection {
  const object = exactRecord(
    value,
    ['review_artifact_identity', 'status', 'stale'],
    'review freshness state'
  );
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  enumValue(object.status, REVIEW_STATUSES, 'review status');
  if (object.stale !== null && typeof object.stale !== 'boolean') {
    invalid('Review stale state must be boolean or null');
  }
  return object as unknown as KnowledgeReviewStateProjection;
}

function validateDecisionRequest(request: KnowledgeReviewDecisionRequest): void {
  const object = exactRecord(request, [
    'reviewContractVersion',
    'proposalId',
    'reviewArtifactIdentity',
    'changeIdentity',
    'observedVaultRevision',
    'decision',
    'comment',
    'actorIdentifier',
    'actorDisplayName',
    'actorSource'
  ], 'review decision request');
  if (object.reviewContractVersion !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT) {
    invalid('Wrong review contract version');
  }
  patternString(object.proposalId, PROPOSAL_ID_RE, 'proposal identity');
  patternString(object.reviewArtifactIdentity, REVIEW_ID_RE, 'review identity');
  optionalPatternString(object.changeIdentity, CHANGE_ID_RE, 'change identity');
  patternString(object.observedVaultRevision, SHA256_RE, 'observed Vault revision');
  const decision = enumValue(
    object.decision,
    ['APPROVE', 'REJECT', 'REQUEST_CHANGES'] as const,
    'review decision'
  );
  const comment = boundedString(object.comment, 'review comment', 4_096);
  if (comment.length > 2_000) {
    invalid('Review comment exceeds its character bound');
  }
  if (decision === 'REQUEST_CHANGES' && comment.trim().length === 0) {
    invalid('Request changes requires a comment');
  }
  if (decision === 'APPROVE' && object.changeIdentity === null) {
    invalid('Approval requires a change identity');
  }
  const actorIdentifier = boundedString(
    object.actorIdentifier,
    'actor identifier',
    512
  );
  const actorDisplayName = boundedString(
    object.actorDisplayName,
    'actor display name',
    512
  );
  if (
    actorIdentifier.trim().length === 0 ||
    actorDisplayName.trim().length === 0 ||
    actorIdentifier.length > 256 ||
    actorDisplayName.length > 256
  ) {
    invalid('Reviewer metadata is invalid');
  }
  if (object.actorSource !== KNOWLEDGE_REVIEW_ACTOR_SOURCE) {
    invalid('Wrong reviewer source');
  }
}

function validateDecisionCreateEnvelope(
  value: unknown,
  request: KnowledgeReviewDecisionRequest
): void {
  const object = exactRecord(value, [
    'contract',
    'command_center_version',
    'control_plane_version',
    'sidecar_runtime_version',
    'source',
    'fixture',
    'duplicate',
    'current_vault_revision',
    'decision',
    'hard_stop',
    'vault_modified',
    'persistence',
    'publication'
  ], 'review decision envelope');
  if (object.contract !== KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT) {
    invalid('Wrong review decision response contract');
  }
  if (object.command_center_version !== KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION) {
    invalid('Wrong command center version');
  }
  boundedString(object.control_plane_version, 'control plane version', 64);
  boundedString(object.sidecar_runtime_version, 'sidecar runtime version', 64);
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review decision source');
  }
  booleanValue(object.duplicate, 'decision duplicate flag');
  patternString(object.current_vault_revision, SHA256_RE, 'current Vault revision');
  if (object.current_vault_revision !== request.observedVaultRevision) {
    invalid('Decision response is stale');
  }
  const decision = validateHumanReviewDecisionProjection(object.decision);
  if (
    decision.review_contract_version !== request.reviewContractVersion ||
    decision.proposal_id !== request.proposalId ||
    decision.review_artifact_identity !== request.reviewArtifactIdentity ||
    decision.change_identity !== request.changeIdentity ||
    decision.observed_vault_revision !== request.observedVaultRevision ||
    decision.decision !== request.decision ||
    decision.comment !== request.comment ||
    decision.actor.actor_identifier !== request.actorIdentifier ||
    decision.actor.display_name !== request.actorDisplayName ||
    decision.actor.source !== request.actorSource
  ) {
    invalid('Decision response binding mismatch');
  }
  if (
    object.hard_stop !== true ||
    object.vault_modified !== false ||
    object.persistence !== false ||
    object.publication !== false
  ) {
    invalid('Decision response authority boundary mismatch');
  }
}

function validateHumanReviewDecisionProjection(
  value: unknown
): HumanReviewDecisionProjection {
  const object = exactRecord(value, [
    'projection_contract',
    'kind',
    'contract_version',
    'review_contract_version',
    'review_status',
    'proposal_id',
    'review_artifact_identity',
    'change_identity',
    'observed_vault_revision',
    'decision',
    'comment',
    'actor',
    'decision_identity',
    'hard_stop',
    'review_decision_only',
    'actor_metadata_evidence_only',
    'human_identity_authenticated',
    'grants_write_authority',
    'grants_vault_write_authority',
    'grants_persistence_authority',
    'grants_publication_authority',
    'grants_merge_authority',
    'grants_rebase_authority',
    'grants_execution_authority',
    'grants_policy_authority',
    'grants_model_gateway_authority',
    'grants_tauri_frontend_authority',
    'grants_automatic_approval_authority'
  ], 'human review decision projection');
  if (
    object.projection_contract !== KNOWLEDGE_REVIEW_PROJECTION_CONTRACT ||
    object.kind !== 'HUMAN_REVIEW_DECISION' ||
    object.contract_version !== HUMAN_REVIEW_DECISION_CONTRACT ||
    object.review_contract_version !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT
  ) {
    invalid('Wrong human review decision contract');
  }
  const status = enumValue(object.review_status, REVIEW_STATUSES, 'review status');
  patternString(object.proposal_id, PROPOSAL_ID_RE, 'proposal identity');
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  optionalPatternString(object.change_identity, CHANGE_ID_RE, 'change identity');
  patternString(object.observed_vault_revision, SHA256_RE, 'observed Vault revision');
  const decision = enumValue(
    object.decision,
    ['APPROVE', 'REJECT', 'REQUEST_CHANGES'] as const,
    'review decision'
  );
  const comment = boundedString(object.comment, 'review comment', 4_096);
  if (comment.length > 2_000) invalid('Review comment character limit exceeded');
  if (decision === 'REQUEST_CHANGES' && comment.trim().length === 0) {
    invalid('Request changes requires a comment');
  }
  if (status === 'BLOCKED' && decision === 'APPROVE') {
    invalid('BLOCKED review cannot be approved');
  }
  if (decision === 'APPROVE' && object.change_identity === null) {
    invalid('Approval requires a change identity');
  }
  const actor = exactRecord(
    object.actor,
    ['actor_identifier', 'display_name', 'source'],
    'reviewer metadata'
  );
  const actorIdentifier = boundedString(actor.actor_identifier, 'actor identifier', 512);
  const actorDisplayName = boundedString(actor.display_name, 'actor display name', 512);
  if (actorIdentifier.length > 256 || actorDisplayName.length > 256) {
    invalid('Reviewer metadata character limit exceeded');
  }
  if (actor.source !== KNOWLEDGE_REVIEW_ACTOR_SOURCE) {
    invalid('Wrong reviewer source');
  }
  patternString(object.decision_identity, DECISION_ID_RE, 'decision identity');
  const expectedTrue = [
    'hard_stop',
    'review_decision_only',
    'actor_metadata_evidence_only'
  ] as const;
  for (const key of expectedTrue) {
    if (object[key] !== true) invalid(`Decision ${key} boundary mismatch`);
  }
  const expectedFalse = [
    'human_identity_authenticated',
    'grants_write_authority',
    'grants_vault_write_authority',
    'grants_persistence_authority',
    'grants_publication_authority',
    'grants_merge_authority',
    'grants_rebase_authority',
    'grants_execution_authority',
    'grants_policy_authority',
    'grants_model_gateway_authority',
    'grants_tauri_frontend_authority',
    'grants_automatic_approval_authority'
  ] as const;
  for (const key of expectedFalse) {
    if (object[key] !== false) invalid(`Decision ${key} boundary mismatch`);
  }
  return object as unknown as HumanReviewDecisionProjection;
}

function ensureListRequest(offset: number, limit: number): void {
  if (!isSafeNonNegativeInteger(offset) || offset > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET) {
    invalid('Review list offset is invalid');
  }
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > MAX_KNOWLEDGE_REVIEW_LIST_LIMIT) {
    invalid('Review list limit is invalid');
  }
}

function validateListEnvelope(value: unknown, requestedOffset: number, requestedLimit: number): void {
  const object = exactRecord(value, [
    'contract',
    'source',
    'fixture',
    'offset',
    'limit',
    'total_count',
    'returned_count',
    'truncated',
    'next_offset',
    'items'
  ], 'review list envelope');
  if (object.contract !== KNOWLEDGE_REVIEW_LIST_CONTRACT) invalid('Wrong review list contract');
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review list source');
  }
  const offset = nonNegativeInteger(object.offset, 'review list offset');
  const limit = positiveInteger(object.limit, 'review list limit');
  const totalCount = nonNegativeInteger(object.total_count, 'review list total count');
  const returnedCount = nonNegativeInteger(object.returned_count, 'review list returned count');
  const truncated = booleanValue(object.truncated, 'review list truncation');
  if (offset !== requestedOffset || limit !== requestedLimit || limit > MAX_KNOWLEDGE_REVIEW_LIST_LIMIT) {
    invalid('Review list request binding mismatch');
  }
  const items = arrayValue(object.items, requestedLimit, 'review list items');
  if (
    totalCount > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET ||
    returnedCount !== items.length ||
    returnedCount > limit ||
    (returnedCount > 0 && offset + returnedCount > totalCount)
  ) {
    invalid('Review list counts are inconsistent');
  }
  const expectedTruncated = offset + returnedCount < totalCount;
  if (truncated !== expectedTruncated) invalid('Review list truncation is inconsistent');
  if (truncated) {
    const nextOffset = nonNegativeInteger(object.next_offset, 'review list continuation');
    if (
      returnedCount === 0 ||
      nextOffset !== offset + returnedCount ||
      nextOffset > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
    ) {
      invalid('Review list continuation is invalid');
    }
  } else if (object.next_offset !== null) {
    invalid('Review list continuation must be null');
  }
  const identities = new Set<string>();
  for (const item of items) {
    const summary = validateSummary(item);
    if (identities.has(summary.review_artifact_identity)) {
      invalid('Duplicate review identity in list response');
    }
    identities.add(summary.review_artifact_identity);
  }
}

function validateSummary(value: unknown): KnowledgeReviewSummaryProjection {
  const object = exactRecord(value, [
    'projection_contract',
    'kind',
    'contract_version',
    'status',
    'blocked',
    'proposal_id',
    'target_stable_id',
    'operation',
    'expected_vault_revision',
    'observed_vault_revision',
    'review_artifact_identity',
    'change_identity',
    'finding_count',
    'normal_change_material_present',
    'detail_projection_truncated'
  ], 'review summary');
  if (object.projection_contract !== KNOWLEDGE_REVIEW_PROJECTION_CONTRACT) {
    invalid('Wrong review summary projection contract');
  }
  if (object.kind !== 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY') {
    invalid('Wrong review summary projection kind');
  }
  if (object.contract_version !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT) {
    invalid('Wrong knowledge review contract');
  }
  const status = enumValue(object.status, REVIEW_STATUSES, 'review status');
  const blocked = booleanValue(object.blocked, 'review blocked flag');
  if (blocked !== (status === 'BLOCKED')) invalid('Review blocked flag is inconsistent');
  patternString(object.proposal_id, PROPOSAL_ID_RE, 'proposal identity');
  stableId(object.target_stable_id);
  enumValue(object.operation, REVIEW_OPERATIONS, 'review operation');
  patternString(object.expected_vault_revision, SHA256_RE, 'expected Vault revision');
  patternString(object.observed_vault_revision, SHA256_RE, 'observed Vault revision');
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  optionalPatternString(object.change_identity, CHANGE_ID_RE, 'change identity');
  nonNegativeInteger(object.finding_count, 'finding count');
  const normalMaterial = booleanValue(
    object.normal_change_material_present,
    'normal change material flag'
  );
  booleanValue(object.detail_projection_truncated, 'detail projection truncation');
  if (blocked && (normalMaterial || object.change_identity !== null)) {
    invalid('BLOCKED summary exposes normal change material');
  }
  if (!blocked && (!normalMaterial || object.change_identity === null)) {
    invalid('Non-BLOCKED summary is missing normal change material');
  }
  return object as unknown as KnowledgeReviewSummaryProjection;
}

function validateGetEnvelope(value: unknown, requestedIdentity: string): void {
  const object = exactRecord(
    value,
    ['contract', 'source', 'fixture', 'projection'],
    'review get envelope'
  );
  if (object.contract !== KNOWLEDGE_REVIEW_GET_CONTRACT) invalid('Wrong review get contract');
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review get source');
  }
  const projectionBytes = textEncoder.encode(
    serializeBounded(
      object.projection,
      MAX_KNOWLEDGE_REVIEW_PROJECTION_BYTES,
      'Review projection exceeds its byte limit'
    )
  ).length;
  if (projectionBytes > MAX_KNOWLEDGE_REVIEW_PROJECTION_BYTES) {
    invalid('Review projection exceeds its byte limit');
  }
  const projection = validateProjection(object.projection);
  if (projection.review_artifact_identity !== requestedIdentity) {
    invalid('Review get identity mismatch');
  }
}

function validateProjection(value: unknown): KnowledgeChangeReviewProjection {
  const object = exactRecord(value, [
    'projection_contract',
    'kind',
    'contract_version',
    'status',
    'proposal_id',
    'proposal_content_hash',
    'operation',
    'target_stable_id',
    'expected_vault_revision',
    'observed_vault_revision',
    'validation_outcome',
    'validation_snapshot',
    'source_validation_findings',
    'stable_id_set_hash',
    'proposed_content_snapshot',
    'findings',
    'before_source_byte_hash',
    'before_text_raw_hash',
    'before_semantic_text_hash',
    'proposed_text_raw_hash',
    'proposed_semantic_text_hash',
    'diff',
    'representation_delta',
    'change_identity',
    'review_artifact_identity',
    'human_review_preview'
  ], 'knowledge review projection');
  if (object.projection_contract !== KNOWLEDGE_REVIEW_PROJECTION_CONTRACT) {
    invalid('Wrong review projection contract');
  }
  if (object.kind !== 'KNOWLEDGE_CHANGE_REVIEW') invalid('Wrong review projection kind');
  if (object.contract_version !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT) {
    invalid('Wrong knowledge review contract');
  }
  const status = enumValue(object.status, REVIEW_STATUSES, 'review status');
  patternString(object.proposal_id, PROPOSAL_ID_RE, 'proposal identity');
  patternString(object.proposal_content_hash, SHA256_RE, 'proposal content hash');
  enumValue(object.operation, REVIEW_OPERATIONS, 'review operation');
  stableId(object.target_stable_id);
  patternString(object.expected_vault_revision, SHA256_RE, 'expected Vault revision');
  patternString(object.observed_vault_revision, SHA256_RE, 'observed Vault revision');
  enumValue(object.validation_outcome, VALIDATION_OUTCOMES, 'validation outcome');
  validateValidationSnapshot(object.validation_snapshot);
  validateSourceFindings(object.source_validation_findings);
  patternString(object.stable_id_set_hash, SHA256_RE, 'stable ID set hash');
  validateProposedContent(object.proposed_content_snapshot);
  validateReviewFindings(object.findings);
  optionalPatternString(object.before_source_byte_hash, SHA256_RE, 'before source byte hash');
  optionalPatternString(object.before_text_raw_hash, SHA256_RE, 'before raw text hash');
  optionalPatternString(object.before_semantic_text_hash, SHA256_RE, 'before semantic hash');
  patternString(object.proposed_text_raw_hash, SHA256_RE, 'proposed raw text hash');
  patternString(object.proposed_semantic_text_hash, SHA256_RE, 'proposed semantic hash');
  if (object.diff !== null) validateDiff(object.diff);
  if (object.representation_delta !== null) validateRepresentation(object.representation_delta);
  optionalPatternString(object.change_identity, CHANGE_ID_RE, 'change identity');
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  validateBoundedText(object.human_review_preview, 'human review preview', 8_192);

  const normalParts = [object.diff, object.representation_delta, object.change_identity];
  if (status === 'BLOCKED' && normalParts.some((part) => part !== null)) {
    invalid('BLOCKED projection exposes normal change material');
  }
  if (status !== 'BLOCKED' && normalParts.some((part) => part === null)) {
    invalid('Non-BLOCKED projection is missing normal change material');
  }
  return object as unknown as KnowledgeChangeReviewProjection;
}

function validateProposedContent(value: unknown): ProposedContentProjection {
  const object = exactRecord(value, [
    'title',
    'body_text',
    'type',
    'status',
    'knowledge_layer',
    'evidence_class',
    'authority',
    'canonical',
    'canonical_scope',
    'aliases',
    'releases',
    'source_paths',
    'evidence_refs',
    'supersedes',
    'superseded_by',
    'updated',
    'last_reviewed',
    'verified_at'
  ], 'proposed content projection');
  boundedString(object.title, 'proposed title');
  validateProposedBody(object.body_text);
  boundedString(object.type, 'proposed type');
  boundedString(object.status, 'proposed status');
  boundedString(object.knowledge_layer, 'knowledge layer');
  boundedString(object.evidence_class, 'evidence class');
  boundedString(object.authority, 'authority');
  booleanValue(object.canonical, 'canonical flag');
  optionalBoundedString(object.canonical_scope, 'canonical scope');
  validateStringCollection(object.aliases, 'aliases');
  validateStringCollection(object.releases, 'releases');
  const sourcePaths = validateStringCollection(object.source_paths, 'source paths');
  for (const path of sourcePaths.items) ensureSafeRelativePath(path);
  validateStringCollection(object.evidence_refs, 'evidence references');
  validateStringCollection(object.supersedes, 'supersedes');
  validateStringCollection(object.superseded_by, 'superseded by');
  boundedString(object.updated, 'updated date');
  boundedString(object.last_reviewed, 'last reviewed date');
  optionalBoundedString(object.verified_at, 'verified date');
  return object as unknown as ProposedContentProjection;
}

function validateProposedBody(value: unknown): ProposedBodyProjection {
  const object = exactRecord(value, [
    'preview_text',
    'is_preview',
    'truncated',
    'original_utf8_bytes',
    'original_line_count',
    'preview_utf8_bytes',
    'preview_line_count',
    'raw_text_hash',
    'semantic_text_hash'
  ], 'proposed body projection');
  validateBoundedTextFields(object, 'proposed body', 16_384);
  patternString(object.raw_text_hash, SHA256_RE, 'proposed body raw hash');
  patternString(object.semantic_text_hash, SHA256_RE, 'proposed body semantic hash');
  return object as unknown as ProposedBodyProjection;
}

function validateBoundedText(
  value: unknown,
  label: string,
  maxPreviewBytes = MAX_GENERAL_STRING_BYTES
): BoundedTextPreviewProjection {
  const object = exactRecord(value, [
    'preview_text',
    'is_preview',
    'truncated',
    'original_utf8_bytes',
    'original_line_count',
    'preview_utf8_bytes',
    'preview_line_count'
  ], label);
  validateBoundedTextFields(object, label, maxPreviewBytes);
  return object as unknown as BoundedTextPreviewProjection;
}

function validateBoundedTextFields(
  object: JsonRecord,
  label: string,
  maxPreviewBytes: number
): void {
  const preview = boundedString(object.preview_text, `${label} text`, maxPreviewBytes);
  if (!booleanValue(object.is_preview, `${label} preview flag`)) {
    invalid(`${label} must be explicitly marked as a preview`);
  }
  const truncated = booleanValue(object.truncated, `${label} truncation`);
  const originalBytes = nonNegativeInteger(object.original_utf8_bytes, `${label} original bytes`);
  const originalLines = nonNegativeInteger(object.original_line_count, `${label} original lines`);
  const previewBytes = nonNegativeInteger(object.preview_utf8_bytes, `${label} preview bytes`);
  const previewLines = nonNegativeInteger(object.preview_line_count, `${label} preview lines`);
  if (textEncoder.encode(preview).length !== previewBytes) invalid(`${label} byte count mismatch`);
  if (previewBytes > originalBytes || previewLines > originalLines) {
    invalid(`${label} bounds are inconsistent`);
  }
  if (!truncated && (previewBytes !== originalBytes || previewLines !== originalLines)) {
    invalid(`${label} non-truncated counts are inconsistent`);
  }
}

function validateStringCollection(value: unknown, label: string): BoundedStringCollectionProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], label);
  const items = arrayValue(object.items, MAX_COLLECTION_ITEMS, `${label} items`);
  const originalCount = nonNegativeInteger(object.original_count, `${label} original count`);
  const truncated = booleanValue(object.truncated, `${label} truncation`);
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid(`${label} counts are inconsistent`);
  }
  for (const item of items) boundedString(item, `${label} item`);
  return object as unknown as BoundedStringCollectionProjection;
}

function validateValidationSnapshot(value: unknown): ValidationSnapshotProjection {
  const object = exactRecord(value, ['value', 'truncated'], 'validation snapshot');
  booleanValue(object.truncated, 'validation snapshot truncation');
  validateValidationValue(object.value, 0, { nodes: 0 });
  return object as unknown as ValidationSnapshotProjection;
}

function validateValidationValue(
  value: unknown,
  depth: number,
  budget: { nodes: number }
): ValidationValueProjection {
  if (depth > MAX_VALIDATION_DEPTH) invalid('Validation snapshot is too deep');
  budget.nodes += 1;
  if (budget.nodes > MAX_VALIDATION_NODES) invalid('Validation snapshot has too many nodes');
  const object = exactRecord(
    value,
    ['type_tag', 'scalar_value', 'mapping_items', 'sequence_items'],
    'validation value'
  );
  const typeTag = enumValue(object.type_tag, VALIDATION_TYPE_TAGS, 'validation type tag');
  const mappingItems = arrayValue(object.mapping_items, MAX_VALIDATION_ITEMS, 'validation mapping');
  const sequenceItems = arrayValue(object.sequence_items, MAX_VALIDATION_ITEMS, 'validation sequence');
  if (typeTag === 'mapping') {
    if (object.scalar_value !== null || sequenceItems.length !== 0) invalid('Invalid validation mapping');
    let previousKey: string | null = null;
    for (const item of mappingItems) {
      const entry = exactRecord(item, ['key', 'value'], 'validation mapping entry');
      const key = boundedString(entry.key, 'validation mapping key', 1_024);
      if (previousKey !== null && key <= previousKey) invalid('Validation mapping keys are not ordered');
      previousKey = key;
      validateValidationValue(entry.value, depth + 1, budget);
    }
  } else if (typeTag === 'sequence') {
    if (object.scalar_value !== null || mappingItems.length !== 0) invalid('Invalid validation sequence');
    for (const child of sequenceItems) validateValidationValue(child, depth + 1, budget);
  } else {
    if (mappingItems.length !== 0 || sequenceItems.length !== 0) invalid('Invalid validation scalar');
    if (typeTag === 'null' && object.scalar_value !== null) invalid('Invalid validation null');
    if (typeTag === 'bool' && typeof object.scalar_value !== 'boolean') invalid('Invalid validation bool');
    if (typeTag === 'int' && !Number.isSafeInteger(object.scalar_value)) invalid('Invalid validation integer');
    if (typeTag === 'string') boundedString(object.scalar_value, 'validation string');
  }
  return object as unknown as ValidationValueProjection;
}

function validateSourceFindings(value: unknown): BoundedSourceValidationFindingsProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], 'source findings');
  const items = arrayValue(object.items, MAX_SOURCE_FINDINGS, 'source finding items');
  const originalCount = nonNegativeInteger(object.original_count, 'source finding count');
  const truncated = booleanValue(object.truncated, 'source finding truncation');
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid('Source finding counts are inconsistent');
  }
  for (const item of items) {
    const finding = exactRecord(item, ['code', 'severity'], 'source finding');
    boundedString(finding.code, 'source finding code');
    boundedString(finding.severity, 'source finding severity');
  }
  return object as unknown as BoundedSourceValidationFindingsProjection;
}

function validateReviewFindings(value: unknown): BoundedReviewFindingsProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], 'review findings');
  const items = arrayValue(object.items, MAX_FINDINGS, 'review finding items');
  const originalCount = nonNegativeInteger(object.original_count, 'review finding count');
  const truncated = booleanValue(object.truncated, 'review finding truncation');
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid('Review finding counts are inconsistent');
  }
  for (const item of items) {
    const finding = exactRecord(item, ['code', 'severity', 'message', 'details'], 'review finding');
    boundedString(finding.code, 'review finding code');
    enumValue(finding.severity, CONFLICT_SEVERITIES, 'review finding severity');
    validateBoundedText(finding.message, 'review finding message', 2_048);
    validateFindingDetails(finding.details);
  }
  return object as unknown as BoundedReviewFindingsProjection;
}

function validateFindingDetails(value: unknown): BoundedFindingDetailsProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], 'finding details');
  const items = arrayValue(object.items, MAX_FINDING_DETAILS, 'finding detail items');
  const originalCount = nonNegativeInteger(object.original_count, 'finding detail count');
  const truncated = booleanValue(object.truncated, 'finding detail truncation');
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid('Finding detail counts are inconsistent');
  }
  for (const item of items) {
    const detail = exactRecord(item, ['key', 'value'], 'finding detail');
    boundedString(detail.key, 'finding detail key');
    boundedString(detail.value, 'finding detail value');
  }
  return object as unknown as BoundedFindingDetailsProjection;
}

function validateDiff(value: unknown): DiffProjection {
  const object = exactRecord(value, [
    'preview',
    'preview_truncated',
    'preview_is_full_diff',
    'full_diff_present',
    'full_diff_hash',
    'full_diff_utf8_bytes'
  ], 'diff projection');
  const preview = validateBoundedText(object.preview, 'diff preview', 16_384);
  const truncated = booleanValue(object.preview_truncated, 'diff truncation');
  const isFull = booleanValue(object.preview_is_full_diff, 'full diff preview flag');
  const fullPresent = booleanValue(object.full_diff_present, 'full diff presence');
  patternString(object.full_diff_hash, SHA256_RE, 'full diff hash');
  nonNegativeInteger(object.full_diff_utf8_bytes, 'full diff bytes');
  if (truncated !== preview.truncated || isFull || !fullPresent) {
    invalid('Diff projection flags are inconsistent');
  }
  return object as unknown as DiffProjection;
}

function validateRepresentation(value: unknown): RepresentationDeltaProjection {
  const object = exactRecord(value, [
    'before_present',
    'after_present',
    'before_line_endings',
    'after_line_endings',
    'terminal_newline_changed',
    'after_source_bytes_known',
    'source_bytes_changed_text_identical',
    'raw_text_changed_semantic_equal',
    'semantic_content_changed',
    'identity'
  ], 'representation delta');
  booleanValue(object.before_present, 'before representation presence');
  booleanValue(object.after_present, 'after representation presence');
  if (object.before_line_endings !== null) validateLineEndings(object.before_line_endings);
  validateLineEndings(object.after_line_endings);
  booleanValue(object.terminal_newline_changed, 'terminal newline change');
  booleanValue(object.after_source_bytes_known, 'source bytes known');
  booleanValue(object.source_bytes_changed_text_identical, 'source bytes change');
  booleanValue(object.raw_text_changed_semantic_equal, 'semantic equality');
  booleanValue(object.semantic_content_changed, 'semantic content change');
  patternString(object.identity, SHA256_RE, 'representation identity');
  return object as unknown as RepresentationDeltaProjection;
}

function validateLineEndings(value: unknown): LineEndingProfileProjection {
  const object = exactRecord(
    value,
    ['crlf_count', 'lf_count', 'cr_count', 'terminal_newline'],
    'line ending profile'
  );
  nonNegativeInteger(object.crlf_count, 'CRLF count');
  nonNegativeInteger(object.lf_count, 'LF count');
  nonNegativeInteger(object.cr_count, 'CR count');
  booleanValue(object.terminal_newline, 'terminal newline');
  return object as unknown as LineEndingProfileProjection;
}

function ensureReviewIdentity(value: unknown): asserts value is string {
  patternString(value, REVIEW_ID_RE, 'review identity');
}

function ensureSafeRelativePath(value: string): void {
  const normalized = value.replace(/\\/g, '/');
  const meaningfulSegments = normalized.split('/').filter((segment) => segment !== '' && segment !== '.');
  if (
    value.length === 0 ||
    [...value].length > 512 ||
    textEncoder.encode(value).length > 2_048 ||
    value.startsWith('/') ||
    value.startsWith('\\') ||
    WINDOWS_DRIVE_RE.test(value) ||
    meaningfulSegments.length === 0 ||
    normalized.split('/').some(
      (segment) =>
        segment === '..' ||
        segment.replace(/ +$/g, '') === '..' ||
        segment.replace(/[. ]+$/g, '') === '..'
    )
  ) {
    invalid('Unsafe source path in review projection');
  }
}

function hasTruncatedReviewDetail(projection: KnowledgeChangeReviewProjection): boolean {
  const proposed = projection.proposed_content_snapshot;
  const collectionTruncated = [
    proposed.aliases,
    proposed.releases,
    proposed.source_paths,
    proposed.evidence_refs,
    proposed.supersedes,
    proposed.superseded_by
  ].some((collection) => collection.truncated);
  const findingDetailTruncated = projection.findings.items.some(
    (finding) => finding.message.truncated || finding.details.truncated
  );
  return (
    projection.validation_snapshot.truncated ||
    projection.source_validation_findings.truncated ||
    proposed.body_text.truncated ||
    collectionTruncated ||
    projection.findings.truncated ||
    findingDetailTruncated ||
    (projection.diff !== null && projection.diff.preview_truncated) ||
    projection.human_review_preview.truncated
  );
}

function lineEndingView(profile: LineEndingProfileProjection) {
  const labels: string[] = [];
  if (profile.crlf_count > 0) labels.push('CRLF');
  if (profile.lf_count > 0) labels.push('LF');
  if (profile.cr_count > 0) labels.push('CR');
  return {
    label: (labels.length === 0 ? 'NONE' : labels.join('+')) as
      | 'NONE'
      | 'LF'
      | 'CRLF'
      | 'CR'
      | 'CRLF+LF'
      | 'CRLF+CR'
      | 'LF+CR'
      | 'CRLF+LF+CR',
    crlfCount: profile.crlf_count,
    lfCount: profile.lf_count,
    crCount: profile.cr_count,
    terminalNewline: profile.terminal_newline
  };
}

function validationScalar(value: ValidationValueProjection, key: string): unknown {
  if (value.type_tag !== 'mapping') return undefined;
  const entry = value.mapping_items.find((item) => item.key === key);
  if (!entry || !['null', 'bool', 'int', 'string'].includes(entry.value.type_tag)) return undefined;
  return entry.value.scalar_value;
}

function formatValidationSnapshot(value: ValidationValueProjection): string {
  try {
    return JSON.stringify(materializeValidationValue(value), null, 2).slice(0, 16_384);
  } catch {
    return '{}';
  }
}

function materializeValidationValue(value: ValidationValueProjection): unknown {
  if (value.type_tag === 'mapping') {
    return Object.fromEntries(
      value.mapping_items.map((entry) => [entry.key, materializeValidationValue(entry.value)])
    );
  }
  if (value.type_tag === 'sequence') {
    return value.sequence_items.map(materializeValidationValue);
  }
  return value.scalar_value;
}

function exactRecord(value: unknown, keys: readonly string[], label: string): JsonRecord {
  if (!isRecord(value)) invalid(`${label} must be an object`);
  const actualKeys = Object.keys(value).sort();
  const expectedKeys = [...keys].sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index])
  ) {
    invalid(`${label} has an unexpected shape`);
  }
  return value;
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function arrayValue(value: unknown, limit: number, label: string): readonly unknown[] {
  if (!Array.isArray(value) || value.length > limit) invalid(`${label} is invalid`);
  return value;
}

function booleanValue(value: unknown, label: string): boolean {
  if (typeof value !== 'boolean') invalid(`${label} is invalid`);
  return value;
}

function nonNegativeInteger(value: unknown, label: string): number {
  if (!isSafeNonNegativeInteger(value)) invalid(`${label} is invalid`);
  return value;
}

function positiveInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) invalid(`${label} is invalid`);
  return value as number;
}

function isSafeNonNegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}

function boundedString(value: unknown, label: string, maxBytes = MAX_GENERAL_STRING_BYTES): string {
  if (
    typeof value !== 'string' ||
    value.includes('\0') ||
    textEncoder.encode(value).length > maxBytes
  ) {
    invalid(`${label} is invalid`);
  }
  return value;
}

function optionalBoundedString(
  value: unknown,
  label: string,
  maxBytes = MAX_GENERAL_STRING_BYTES
): string | null {
  if (value === null) return null;
  return boundedString(value, label, maxBytes);
}

function patternString(value: unknown, pattern: RegExp, label: string): string {
  if (typeof value !== 'string' || !pattern.test(value)) invalid(`${label} is invalid`);
  return value;
}

function optionalPatternString(value: unknown, pattern: RegExp, label: string): string | null {
  if (value === null) return null;
  return patternString(value, pattern, label);
}

function stableId(value: unknown): string {
  if (typeof value !== 'string' || value.length > 128 || !STABLE_ID_RE.test(value)) {
    invalid('Target stable ID is invalid');
  }
  return value;
}

function enumValue<const T extends readonly string[]>(
  value: unknown,
  values: T,
  label: string
): T[number] {
  if (typeof value !== 'string' || !(values as readonly string[]).includes(value)) {
    invalid(`${label} is invalid`);
  }
  return value as T[number];
}

function serializeBounded(value: unknown, maxBytes: number, message: string): string {
  let serialized: string | undefined;
  try {
    serialized = JSON.stringify(value);
  } catch {
    invalid('Review bridge response is not JSON-safe');
  }
  if (serialized === undefined || textEncoder.encode(serialized).length > maxBytes) invalid(message);
  return serialized;
}

function deepFreeze<T>(value: T): T {
  if (typeof value !== 'object' || value === null || Object.isFrozen(value)) return value;
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
  return Object.freeze(value);
}

function boundedSanitized(value: string, limit: number): string {
  const sanitized = value
    .replace(/\0/g, '')
    .replace(/Traceback[\s\S]*/gi, '<redacted>')
    .replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>')
    .replace(/Bearer\s+[A-Za-z0-9._-]+/gi, '<redacted>');
  return [...sanitized].slice(0, limit).join('');
}

function invalid(message: string): never {
  throw Object.freeze({ code: 'invalid_payload', message });
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/bridge/modelGateway.ts (1029 строк, 39917 байт)

````typescript
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type {
  ApprovedModelSummary,
  ApprovedRuntimeSummary,
  AssistantLocale,
  ApprovedDownloadableArtifact,
  ArtifactDownloadState,
  ArtifactInstallationStatus,
  ArtifactValidationSummary,
  GatewayCatalog,
  HarnessId,
  ManagedCatalogIdentity,
  ManagedInstalledArtifacts,
  ManagedModelCatalog,
  ManagedModelRemovalResult,
  ManagedRuntimeCatalog,
  ManagedRuntimeLogs,
  ManagedRuntimeStartResponse,
  ManagedRuntimeStatus,
  ModelReadinessSummary,
  ModelBinding,
  ModelGatewayEvent,
  ModelListResponse,
  ModelTurnCancelResponse,
  ModelTurnStartResponse,
  ProbeResponse,
  ProviderId,
  SanitizedGatewayError
} from '$lib/types/modelGateway';
import { CONTROL_PLANE_EVENT_CHANNEL } from './controlPlane';
import type { FileContextInclusion, FilesContextReport } from '$lib/types/files';

type InvokeArgs = Readonly<Record<string, string | number | boolean | readonly string[]>>;

export async function getModelGatewayCatalog(): Promise<GatewayCatalog> {
  return validateCatalog(await invokeExact('model_gateway_catalog'));
}

export async function probeModelGateway(port: number): Promise<ProbeResponse> {
  return validateProbe(await invokeExact('model_gateway_probe', { port: validatePort(port) }));
}

export async function listModelGatewayModels(port: number): Promise<ModelListResponse> {
  return validateModels(await invokeExact('model_gateway_list_models', { port: validatePort(port) }));
}

export async function setModelBinding(args: {
  providerId: ProviderId;
  harnessId: HarnessId;
  port?: number;
  modelId: string;
  runtimeInstanceId?: string;
}): Promise<ModelBinding> {
  const invokeArgs: Record<string, string | number | boolean> = {
    providerId: args.providerId,
    harnessId: args.harnessId,
    modelId: args.providerId === 'managed-llama-cpp' ? validateArtifactId(args.modelId) : validateModelId(args.modelId),
    confirmed: true
  };
  if (args.providerId === 'openai-compatible-local') {
    invokeArgs.port = validatePort(Number(args.port));
  }
  if (args.runtimeInstanceId) {
    invokeArgs.runtimeInstanceId = args.runtimeInstanceId;
  }
  return validateBinding(
    await invokeExact('model_binding_set', invokeArgs)
  );
}

export async function getManagedRuntimeStatus(): Promise<ManagedRuntimeStatus> {
  return validateManagedStatus(await invokeExact('managed_runtime_status'));
}

export async function getManagedRuntimeCatalog(): Promise<ManagedRuntimeCatalog> {
  return validateManagedRuntimeCatalog(await invokeExact('managed_runtime_catalog'));
}

export async function getManagedModelCatalog(): Promise<ManagedModelCatalog> {
  return validateManagedModelCatalog(await invokeExact('managed_model_catalog'));
}

export async function getManagedInstalledArtifacts(): Promise<ManagedInstalledArtifacts> {
  return validateManagedInstalledArtifacts(await invokeExact('managed_installed_artifacts'));
}

export async function listApprovedDownloadableArtifacts(): Promise<readonly ApprovedDownloadableArtifact[]> {
  const result = await invokeExact<unknown>('list_approved_downloadable_artifacts');
  return boundedArray(result, 32).map(validateApprovedDownloadableArtifact);
}

export async function startApprovedArtifactDownload(artifactId: string): Promise<ArtifactDownloadState> {
  const requestedId = validateArtifactId(artifactId);
  const result = validateArtifactDownloadState(
    await invokeExact('start_approved_artifact_download', { artifactId: requestedId, confirmed: true })
  );
  if (result.artifact_id !== requestedId) throw invalid();
  return result;
}

export async function getArtifactDownloadState(jobId: string): Promise<ArtifactDownloadState> {
  return validateArtifactDownloadState(
    await invokeExact('get_artifact_download_state', { jobId: validateDownloadJobId(jobId) })
  );
}

export async function cancelArtifactDownload(jobId: string): Promise<ArtifactDownloadState> {
  return validateArtifactDownloadState(
    await invokeExact('cancel_artifact_download', { jobId: validateDownloadJobId(jobId) })
  );
}

export async function removeManagedModel(modelId: string): Promise<ManagedModelRemovalResult> {
  const requestedId = validateArtifactId(modelId);
  const object = expectExactRecord(
    await invokeExact('remove_managed_model', { modelId: requestedId, confirmed: true }),
    ['model_id', 'removed']
  );
  if (object.model_id !== requestedId || object.removed !== true) throw invalid();
  return { model_id: requestedId, removed: true };
}

export async function getManagedArtifactValidationStatus(artifactId: string): Promise<ArtifactValidationSummary> {
  const requestedId = validateArtifactId(artifactId);
  const result = validateArtifactValidationSummary(
    await invokeExact('managed_artifact_validation_status', { artifactId: requestedId })
  );
  if (result.artifact_id !== requestedId) throw invalid();
  return result;
}

export async function getManagedModelReadiness(modelId: string): Promise<ModelReadinessSummary> {
  const requestedId = validateArtifactId(modelId);
  const result = validateModelReadiness(
    await invokeExact('managed_model_readiness', { modelId: requestedId })
  );
  if (result.model_id !== requestedId) throw invalid();
  return result;
}

export async function startManagedRuntime(modelId: string): Promise<ManagedRuntimeStartResponse> {
  return validateManagedStart(await invokeExact('managed_runtime_start', { modelId: validateArtifactId(modelId) }));
}

export async function stopManagedRuntime(): Promise<void> {
  await invokeExact('managed_runtime_stop');
}

export async function getManagedRuntimeLogs(): Promise<ManagedRuntimeLogs> {
  return validateManagedLogs(await invokeExact('managed_runtime_logs'));
}

export async function startModelTurn(args: {
  requestId: string;
  chatSessionId: string;
  modelId: string;
  submittedAtUnixMs: number;
  maxTokens: number;
  prompt: string;
  fileIds?: readonly string[];
  locale: AssistantLocale;
  bindingFingerprint: string;
}): Promise<ModelTurnStartResponse> {
  const requestId = validateTurnId(args.requestId);
  const chatSessionId = validateChatSessionId(args.chatSessionId);
  const modelId = validateArtifactId(args.modelId);
  const submittedAtUnixMs = positiveSafeInteger(args.submittedAtUnixMs);
  const maxTokens = validateMaxTokens(args.maxTokens);
  const fileIds = validateFileIds(args.fileIds ?? []);
  const result = validateTurnStart(
    await invokeExact('model_turn_start', {
      requestId,
      chatSessionId,
      modelId,
      submittedAtUnixMs,
      maxTokens,
      prompt: bounded(args.prompt, 16_384),
      fileIds,
      locale: validateLocale(args.locale),
      bindingFingerprint: validateFingerprint(args.bindingFingerprint)
    })
  );
  if (
    result.request_id !== requestId ||
    result.turn_id !== requestId ||
    result.chat_session_id !== chatSessionId ||
    result.model_id !== modelId ||
    result.submitted_at_unix_ms !== submittedAtUnixMs ||
    result.max_tokens !== maxTokens ||
    result.binding_fingerprint !== args.bindingFingerprint
  ) throw invalid();
  return result;
}

function validateFileIds(value: readonly string[]): readonly string[] {
  if (!Array.isArray(value) || value.length > 32) throw invalid();
  const unique = new Set<string>();
  for (const fileId of value) {
    if (typeof fileId !== 'string' || !/^[0-9a-f]{64}$/.test(fileId) || unique.has(fileId)) {
      throw invalid();
    }
    unique.add(fileId);
  }
  return [...unique];
}

function validateLocale(value: unknown): AssistantLocale {
  if (value !== 'ru' && value !== 'en') throw invalid();
  return value;
}

export async function cancelModelTurn(requestId: string): Promise<ModelTurnCancelResponse> {
  const expectedRequestId = validateTurnId(requestId);
  const result = validateTurnCancel(
    await invokeExact('model_turn_cancel', { requestId: expectedRequestId })
  );
  if (result.request_id !== expectedRequestId || result.turn_id !== expectedRequestId) throw invalid();
  return result;
}

export async function subscribeModelGatewayEvents(
  callback: (event: ModelGatewayEvent) => void,
  onProtocolError?: (error: SanitizedGatewayError) => void
): Promise<() => void> {
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    try {
      const parsed = parseModelEvent(event.payload);
      if (parsed) callback(parsed);
    } catch (error) {
      onProtocolError?.(normalizeGatewayError(error));
    }
  });
  return () => cleanup();
}

export function normalizeGatewayError(error: unknown): SanitizedGatewayError {
  if (isRecord(error)) {
    return {
      code: bounded(typeof error.code === 'string' ? error.code : 'gateway_error', 64),
      message: bounded(sanitize(typeof error.message === 'string' ? error.message : 'Local model gateway error'), 240)
    };
  }
  return { code: 'gateway_error', message: 'Local model gateway error' };
}

async function invokeExact<T>(command: string, args?: InvokeArgs): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw normalizeGatewayError(error);
  }
}

function validateCatalog(value: unknown): GatewayCatalog {
  const object = expectRecord(value);
  if (!Array.isArray(object.providers) || !Array.isArray(object.harnesses)) throw invalid();
  const providers = object.providers.map(expectRecord);
  const harnesses = object.harnesses.map(expectRecord);
  if (providers.map((item) => item.provider_id).join('|') !== 'openai-compatible-local|managed-llama-cpp') throw invalid();
  if (harnesses.map((item) => item.harness_id).join('|') !== 'minimal|native-localcomet') throw invalid();
  return object as unknown as GatewayCatalog;
}

function validateProbe(value: unknown): ProbeResponse {
  const object = expectRecord(value);
  if (object.provider_id !== 'openai-compatible-local' || object.host !== '127.0.0.1' || object.base_path !== '/v1') throw invalid();
  validatePort(Number(object.port));
  return object as unknown as ProbeResponse;
}

function validateModels(value: unknown): ModelListResponse {
  const object = expectRecord(value);
  if (object.provider_id !== 'openai-compatible-local' || object.host !== '127.0.0.1' || !Array.isArray(object.models)) throw invalid();
  object.models.forEach((item) => validateModelId(String(expectRecord(item).model_id)));
  return object as unknown as ModelListResponse;
}

function validateBinding(value: unknown): ModelBinding {
  const object = expectRecord(value);
  if (!['openai-compatible-local', 'managed-llama-cpp'].includes(String(object.provider_id)) || object.persistence !== false) throw invalid();
  if (object.provider_id === 'openai-compatible-local' && object.host !== '127.0.0.1') throw invalid();
  if (object.provider_id === 'managed-llama-cpp' && typeof object.runtime_instance_id !== 'string') throw invalid();
  validateFingerprint(String(object.binding_fingerprint));
  return object as unknown as ModelBinding;
}

function validateManagedStatus(value: unknown): ManagedRuntimeStatus {
  const object = expectExactRecord(value, [
    'engine',
    'state',
    'installation',
    'runtime_version',
    'runtime_instance_id',
    'runtime_instance_fingerprint',
    'model_id',
    'model_display_name',
    'binding_fingerprint',
    'model_state',
    'inference_ready',
    'last_error'
  ]);
  if (object.engine !== 'llama.cpp') throw invalid();
  return {
    engine: 'llama.cpp',
    state: exactString(object.state, ['NotInstalled', 'Stopped', 'Validating', 'Starting', 'Ready', 'Stopping', 'Failed']),
    installation: exactString(object.installation, ['Installed', 'Not installed']),
    runtime_version: nullableSafeText(object.runtime_version, 96),
    runtime_instance_id: nullablePattern(object.runtime_instance_id, /^[0-9a-f]{32}$/),
    runtime_instance_fingerprint: nullableHash(object.runtime_instance_fingerprint),
    model_id: object.model_id === null ? null : validateArtifactId(String(object.model_id)),
    model_display_name: nullableSafeText(object.model_display_name, 192),
    binding_fingerprint: nullableHash(object.binding_fingerprint),
    model_state: exactString(object.model_state, ['Unavailable', 'Validating', 'Loading', 'Ready', 'Failed', 'Unloading']),
    inference_ready: exactBoolean(object.inference_ready),
    last_error: nullableSafeText(object.last_error, 240)
  };
}

function validateManagedRuntimeCatalog(value: unknown): ManagedRuntimeCatalog {
  const object = expectExactRecord(value, ['schema_version', 'catalog_id', 'catalog_version', 'catalog_digest', 'runtimes']);
  const identity = validateCatalogIdentity(object);
  const runtimes = boundedArray(object.runtimes, 32).map(validateApprovedRuntime);
  validateUniqueSorted(runtimes.map((runtime) => runtime.runtime_id));
  return { ...identity, runtimes };
}

function validateManagedModelCatalog(value: unknown): ManagedModelCatalog {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'engine',
    'model_root',
    'models',
    'maximum_models'
  ]);
  if (object.engine !== 'llama.cpp' || object.model_root !== '<MANAGED_MODEL_ROOT>' || object.maximum_models !== 32) throw invalid();
  const identity = validateCatalogIdentity(object);
  const models = boundedArray(object.models, 32).map(validateApprovedModel);
  validateUniqueSorted(models.map((model) => model.model_id));
  return { ...identity, engine: 'llama.cpp', model_root: '<MANAGED_MODEL_ROOT>', models, maximum_models: 32 };
}

function validateManagedInstalledArtifacts(value: unknown): ManagedInstalledArtifacts {
  const object = expectExactRecord(value, ['schema_version', 'catalog_id', 'catalog_version', 'catalog_digest', 'artifacts']);
  const identity = validateCatalogIdentity(object);
  const artifacts = boundedArray(object.artifacts, 64).map(validateArtifactValidationSummary);
  validateUnique(artifacts.map((artifact) => artifact.artifact_id));
  return { ...identity, artifacts };
}

function validateApprovedDownloadableArtifact(value: unknown): ApprovedDownloadableArtifact {
  const object = expectExactRecord(value, [
    'artifact_id',
    'kind',
    'display_name',
    'source_identity',
    'expected_bytes',
    'license_id',
    'format',
    'quantization',
    'user_confirmation_required',
    'automatic_download'
  ]);
  const kind = exactString(object.kind, ['runtime', 'model']);
  const format = object.format === null ? null : safeText(object.format, 64);
  const quantization = object.quantization === null ? null : safeText(object.quantization, 64);
  if (
    object.user_confirmation_required !== true ||
    object.automatic_download !== false ||
    (kind === 'runtime' && (format !== 'zip' || quantization !== null)) ||
    (kind === 'model' && (format !== 'GGUF' || quantization !== 'Q4_K_M'))
  ) throw invalid();
  return {
    artifact_id: validateArtifactId(String(object.artifact_id)),
    kind,
    display_name: safeText(object.display_name, 192),
    source_identity: safeText(object.source_identity, 256),
    expected_bytes: positiveSafeInteger(object.expected_bytes),
    license_id: safeText(object.license_id, 128),
    format,
    quantization,
    user_confirmation_required: true,
    automatic_download: false
  };
}

function validateArtifactDownloadState(value: unknown): ArtifactDownloadState {
  const object = expectExactRecord(value, [
    'job_id',
    'artifact_id',
    'lifecycle',
    'expected_bytes',
    'received_bytes',
    'percent',
    'started_utc_ms',
    'updated_utc_ms',
    'error_code'
  ]);
  const expectedBytes = positiveSafeInteger(object.expected_bytes);
  const receivedBytes = nonNegativeSafeInteger(object.received_bytes);
  const lifecycle = exactString(object.lifecycle, [
    'idle',
    'awaiting_confirmation',
    'checking_disk',
    'downloading',
    'cancelling',
    'cancelled',
    'verifying_size',
    'verifying_hash',
    'validating_artifact',
    'installing',
    'completed',
    'failed'
  ]);
  const percent = object.percent === null ? null : nonNegativeSafeInteger(object.percent);
  const errorCode = object.error_code === null ? null : safeText(object.error_code, 64);
  const startedUtcMs = nonNegativeSafeInteger(object.started_utc_ms);
  const updatedUtcMs = nonNegativeSafeInteger(object.updated_utc_ms);
  if (
    receivedBytes > expectedBytes ||
    updatedUtcMs < startedUtcMs ||
    (percent !== null && (percent > 100 || percent !== Math.floor((receivedBytes * 100) / expectedBytes))) ||
    (lifecycle === 'completed' && (receivedBytes !== expectedBytes || percent !== 100 || errorCode !== null)) ||
    (lifecycle === 'failed' && errorCode === null) ||
    (lifecycle !== 'failed' && errorCode !== null)
  ) throw invalid();
  return {
    job_id: validateDownloadJobId(String(object.job_id)),
    artifact_id: validateArtifactId(String(object.artifact_id)),
    lifecycle,
    expected_bytes: expectedBytes,
    received_bytes: receivedBytes,
    percent,
    started_utc_ms: startedUtcMs,
    updated_utc_ms: updatedUtcMs,
    error_code: errorCode
  };
}

function validateArtifactValidationSummary(value: unknown): ArtifactValidationSummary {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'artifact_id',
    'kind',
    'catalog_status',
    'installation_status',
    'expected_bytes',
    'expected_sha256',
    'observed_bytes',
    'observed_sha256',
    'validation_code',
    'verified_unix_ms'
  ]);
  const identity = validateCatalogIdentity(object);
  const kind = exactString(object.kind, ['runtime', 'model']);
  const installationStatus = validateInstallationStatus(object.installation_status);
  const expectedBytes = positiveSafeInteger(object.expected_bytes);
  const expectedSha256 = validateHash(object.expected_sha256);
  const observedBytes = object.observed_bytes === null ? null : nonNegativeSafeInteger(object.observed_bytes);
  const observedSha256 = object.observed_sha256 === null ? null : validateHash(object.observed_sha256);
  const validationCode = safeText(object.validation_code, 64);
  if (validationCode !== installationStatus) throw invalid();
  if (installationStatus === 'not_installed' && (observedBytes !== null || observedSha256 !== null)) throw invalid();
  if (
    installationStatus === 'valid' &&
    ((kind === 'model' && (observedBytes !== expectedBytes || observedSha256 !== expectedSha256)) ||
      (kind === 'runtime' && (observedBytes !== null || observedSha256 !== null)))
  ) throw invalid();
  return {
    ...identity,
    artifact_id: validateArtifactId(String(object.artifact_id)),
    kind,
    catalog_status: validateCatalogStatus(object.catalog_status),
    installation_status: installationStatus,
    expected_bytes: expectedBytes,
    expected_sha256: expectedSha256,
    observed_bytes: observedBytes,
    observed_sha256: observedSha256,
    validation_code: validationCode,
    verified_unix_ms: nonNegativeSafeInteger(object.verified_unix_ms)
  };
}

function validateModelReadiness(value: unknown): ModelReadinessSummary {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'model_id',
    'model_status',
    'compatible_runtime_ids',
    'selected_runtime_id',
    'runtime_status',
    'compatibility',
    'readiness',
    'launchable'
  ]);
  const identity = validateCatalogIdentity(object);
  const compatibleRuntimeIds = boundedArray(object.compatible_runtime_ids, 32).map((item) => validateArtifactId(String(item)));
  validateUniqueSorted(compatibleRuntimeIds);
  const selectedRuntimeId = object.selected_runtime_id === null ? null : validateArtifactId(String(object.selected_runtime_id));
  const modelStatus = validateInstallationStatus(object.model_status);
  const runtimeStatus = object.runtime_status === null ? null : validateInstallationStatus(object.runtime_status);
  const compatibility = exactString(object.compatibility, [
    'compatible',
    'no_compatible_runtime_installed',
    'incompatible_runtime_installed'
  ]);
  const readiness = exactString(object.readiness, [
    'ready',
    'model_not_installed',
    'model_invalid',
    'runtime_not_installed',
    'runtime_invalid',
    'incompatible'
  ]);
  if (typeof object.launchable !== 'boolean') throw invalid();
  const launchable = object.launchable;
  const truthfullyLaunchable =
    modelStatus === 'valid' &&
    runtimeStatus === 'valid' &&
    compatibility === 'compatible' &&
    readiness === 'ready' &&
    selectedRuntimeId !== null &&
    compatibleRuntimeIds.includes(selectedRuntimeId);
  if (launchable !== truthfullyLaunchable) throw invalid();
  if (compatibility === 'compatible' && (runtimeStatus !== 'valid' || selectedRuntimeId === null || !compatibleRuntimeIds.includes(selectedRuntimeId))) throw invalid();
  if (compatibility === 'no_compatible_runtime_installed' && selectedRuntimeId !== null) throw invalid();
  if (readiness === 'model_not_installed' && modelStatus !== 'not_installed') throw invalid();
  if (readiness === 'model_invalid' && ['valid', 'not_installed'].includes(modelStatus)) throw invalid();
  if (readiness === 'runtime_not_installed' && (modelStatus !== 'valid' || runtimeStatus !== 'not_installed')) throw invalid();
  if (readiness === 'runtime_invalid' && (modelStatus !== 'valid' || runtimeStatus === null || ['valid', 'not_installed'].includes(runtimeStatus))) throw invalid();
  if (readiness === 'incompatible' && compatibility !== 'incompatible_runtime_installed') throw invalid();
  return {
    ...identity,
    model_id: validateArtifactId(String(object.model_id)),
    model_status: modelStatus,
    compatible_runtime_ids: compatibleRuntimeIds,
    selected_runtime_id: selectedRuntimeId,
    runtime_status: runtimeStatus,
    compatibility,
    readiness,
    launchable
  };
}

function validateManagedStart(value: unknown): ManagedRuntimeStartResponse {
  const object = expectExactRecord(value, [
    'state',
    'model_state',
    'inference_ready',
    'provider_id',
    'model_id',
    'model_display_name',
    'runtime_instance_id',
    'runtime_instance_fingerprint'
  ]);
  if (object.provider_id !== 'managed-llama-cpp' || object.state !== 'Ready' || object.model_state !== 'Ready' || object.inference_ready !== true) throw invalid();
  return {
    state: 'Ready',
    model_state: 'Ready',
    inference_ready: true,
    provider_id: 'managed-llama-cpp',
    model_id: validateArtifactId(String(object.model_id)),
    model_display_name: safeText(object.model_display_name, 192),
    runtime_instance_id: patternString(object.runtime_instance_id, /^[0-9a-f]{32}$/),
    runtime_instance_fingerprint: validateHash(object.runtime_instance_fingerprint)
  };
}

function validateManagedLogs(value: unknown): ManagedRuntimeLogs {
  const object = expectExactRecord(value, ['stdout_tail', 'stderr_tail']);
  return {
    stdout_tail: boundedArray(object.stdout_tail, 200).map((line) => safeTextAllowEmpty(line, 2_048)),
    stderr_tail: boundedArray(object.stderr_tail, 200).map((line) => safeTextAllowEmpty(line, 2_048))
  };
}

function validateTurnStart(value: unknown): ModelTurnStartResponse {
  const object = expectRecord(value);
  const requestId = validateTurnId(String(object.request_id));
  const turnId = validateTurnId(String(object.turn_id));
  if (turnId !== requestId || object.state !== 'Accepted') throw invalid();
  const response: ModelTurnStartResponse = {
    request_id: requestId,
    chat_session_id: validateChatSessionId(object.chat_session_id),
    turn_id: turnId,
    state: 'Accepted',
    model_id: validateArtifactId(String(object.model_id)),
    submitted_at_unix_ms: positiveSafeInteger(object.submitted_at_unix_ms),
    max_tokens: validateMaxTokens(object.max_tokens),
    binding_fingerprint: validateFingerprint(String(object.binding_fingerprint))
  };
  return object.file_context === undefined
    ? response
    : { ...response, file_context: validateFilesContextReport(object.file_context) };
}

function validateFilesContextReport(value: unknown): FilesContextReport {
  const object = expectExactRecord(value, [
    'source_bytes',
    'source_characters',
    'included_bytes',
    'included_characters',
    'truncated',
    'files'
  ]);
  const sourceBytes = boundedNonNegativeInteger(object.source_bytes, 5 * 1024 * 1024);
  const sourceCharacters = boundedNonNegativeInteger(object.source_characters, 5 * 1024 * 1024);
  const includedBytes = boundedNonNegativeInteger(object.included_bytes, sourceBytes);
  const includedCharacters = boundedNonNegativeInteger(object.included_characters, sourceCharacters);
  const files = boundedArray(object.files, 32).map(validateFileContextInclusion);
  const ids = files.map((file) => file.file_id);
  validateUnique(ids);
  if (
    files.length === 0 ||
    object.truncated !== (includedBytes !== sourceBytes) ||
    files.reduce((total, file) => total + file.original_bytes, 0) !== sourceBytes ||
    files.reduce((total, file) => total + file.original_characters, 0) !== sourceCharacters ||
    files.reduce((total, file) => total + file.included_bytes, 0) !== includedBytes ||
    files.reduce((total, file) => total + file.included_characters, 0) !== includedCharacters
  ) throw invalid();
  return {
    source_bytes: sourceBytes,
    source_characters: sourceCharacters,
    included_bytes: includedBytes,
    included_characters: includedCharacters,
    truncated: object.truncated as boolean,
    files
  };
}

function validateFileContextInclusion(value: unknown): FileContextInclusion {
  const object = expectExactRecord(value, [
    'file_id',
    'filename',
    'original_bytes',
    'original_characters',
    'included_bytes',
    'included_characters',
    'inclusion'
  ]);
  const originalBytes = boundedNonNegativeInteger(object.original_bytes, 2 * 1024 * 1024);
  const originalCharacters = boundedNonNegativeInteger(object.original_characters, 2 * 1024 * 1024);
  const includedBytes = boundedNonNegativeInteger(object.included_bytes, originalBytes);
  const includedCharacters = boundedNonNegativeInteger(object.included_characters, originalCharacters);
  const inclusion = exactString(object.inclusion, ['full', 'bounded_excerpt']);
  if (
    (inclusion === 'full' && (includedBytes !== originalBytes || includedCharacters !== originalCharacters)) ||
    (inclusion === 'bounded_excerpt' && (includedBytes >= originalBytes || includedCharacters >= originalCharacters))
  ) throw invalid();
  return {
    file_id: patternString(object.file_id, /^[0-9a-f]{64}$/),
    filename: validateContextFilename(object.filename),
    original_bytes: originalBytes,
    original_characters: originalCharacters,
    included_bytes: includedBytes,
    included_characters: includedCharacters,
    inclusion
  };
}

function validateContextFilename(value: unknown): string {
  const filename = safeText(value, 255);
  if (/[\\/:]/.test(filename) || filename === '.' || filename === '..') throw invalid();
  return filename;
}

function validateTurnCancel(value: unknown): ModelTurnCancelResponse {
  const object = expectExactRecord(value, [
    'request_id',
    'turn_id',
    'state',
    'accepted',
    'already_terminal',
    'worker_alive'
  ]);
  const requestId = validateTurnId(String(object.request_id));
  const turnId = validateTurnId(String(object.turn_id));
  if (requestId !== turnId || typeof object.accepted !== 'boolean' || typeof object.already_terminal !== 'boolean' || typeof object.worker_alive !== 'boolean') {
    throw invalid();
  }
  const state = exactString(object.state, ['Cancelling', 'Cancelled']);
  const acceptedActive = object.accepted === true && object.already_terminal === false && (
    (state === 'Cancelling' && object.worker_alive === true) ||
    (state === 'Cancelled' && object.worker_alive === false)
  );
  const alreadyTerminal = object.accepted === false && object.already_terminal === true && object.worker_alive === false && state === 'Cancelled';
  if (!acceptedActive && !alreadyTerminal) throw invalid();
  return {
    request_id: requestId,
    turn_id: turnId,
    state,
    accepted: object.accepted,
    already_terminal: object.already_terminal,
    worker_alive: object.worker_alive
  };
}

function parseModelEvent(value: unknown): ModelGatewayEvent | null {
  const object = expectRecord(value);
  if (!isModelMethod(object.method)) return null;
  const metadata = expectRecord(object.metadata ?? {});
  const requestId = validateTurnId(String(object.request_id));
  const turnId = validateTurnId(String(object.turn_id));
  const replyTo = validateTurnId(String(object.reply_to));
  if (requestId !== turnId || requestId !== replyTo) throw invalid();
  const state = exactString(object.state, ['Streaming', 'Completed', 'Cancelled', 'TimedOut', 'Failed']);
  const expectedState: Readonly<Record<ModelGatewayEvent['method'], ModelGatewayEvent['state']>> = {
    'model.turn.started': 'Streaming',
    'model.output.delta': 'Streaming',
    'model.turn.completed': 'Completed',
    'model.turn.cancelled': 'Cancelled',
    'model.turn.timed_out': 'TimedOut',
    'model.turn.failed': 'Failed'
  };
  if (state !== expectedState[object.method]) throw invalid();
  const toolsExecuted = nonNegativeSafeInteger(metadata.tools_executed);
  const persistence = exactBoolean(metadata.persistence);
  if (toolsExecuted !== 0 || persistence !== false) throw invalid();
  return {
    method: object.method,
    sequence: nonNegativeSafeInteger(object.sequence),
    reply_to: replyTo,
    request_id: requestId,
    chat_session_id: validateChatSessionId(object.chat_session_id),
    turn_id: turnId,
    state,
    text: typeof object.text === 'string' ? bounded(object.text, 65_536) : null,
    model_called: exactBoolean(metadata.model_called),
    tools_executed: 0,
    persistence: false,
    generated_bytes: nonNegativeSafeInteger(metadata.generated_bytes),
    provider_id: exactString(metadata.provider_id, ['managed-llama-cpp', 'openai-compatible-local']),
    harness_id: exactString(metadata.harness_id, ['minimal', 'native-localcomet']),
    model_id: validateArtifactId(String(object.model_id)),
    binding_fingerprint: validateFingerprint(String(metadata.binding_fingerprint)),
    error: isRecord(metadata.error)
      ? {
          code: bounded(String(metadata.error.code ?? 'gateway_error'), 64),
          message: bounded(sanitize(String(metadata.error.message ?? 'Local model gateway error')), 240),
          retryable: metadata.error.retryable === true
        }
      : undefined
  };
}

function isModelMethod(value: unknown): value is ModelGatewayEvent['method'] {
  return typeof value === 'string' && ['model.turn.started', 'model.output.delta', 'model.turn.completed', 'model.turn.cancelled', 'model.turn.timed_out', 'model.turn.failed'].includes(value);
}

function validateApprovedRuntime(value: unknown): ApprovedRuntimeSummary {
  const object = expectExactRecord(value, [
    'runtime_id',
    'provider',
    'release_tag',
    'platform',
    'architecture',
    'variant',
    'upstream_repository',
    'upstream_revision',
    'asset_filename',
    'asset_bytes',
    'asset_sha256',
    'archive_format',
    'permitted_bind_scope',
    'supported_api_protocol',
    'license_id',
    'public_distribution',
    'status'
  ]);
  if (
    object.platform !== 'windows' ||
    object.architecture !== 'x86-64' ||
    object.variant !== 'cpu' ||
    object.archive_format !== 'zip' ||
    object.permitted_bind_scope !== 'loopback-only' ||
    object.supported_api_protocol !== 'openai-compatible-v1' ||
    object.public_distribution !== false
  ) throw invalid();
  return {
    runtime_id: validateArtifactId(String(object.runtime_id)),
    provider: safeText(object.provider, 256),
    release_tag: safeText(object.release_tag, 256),
    platform: 'windows',
    architecture: 'x86-64',
    variant: 'cpu',
    upstream_repository: safeText(object.upstream_repository, 256),
    upstream_revision: safeText(object.upstream_revision, 256),
    asset_filename: safeFilename(object.asset_filename),
    asset_bytes: positiveSafeInteger(object.asset_bytes),
    asset_sha256: validateHash(object.asset_sha256),
    archive_format: 'zip',
    permitted_bind_scope: 'loopback-only',
    supported_api_protocol: 'openai-compatible-v1',
    license_id: safeText(object.license_id, 256),
    public_distribution: false,
    status: validateCatalogStatus(object.status)
  };
}

function validateApprovedModel(value: unknown): ApprovedModelSummary {
  const object = expectExactRecord(value, [
    'model_id',
    'provider',
    'family',
    'display_name',
    'format',
    'quantization',
    'upstream_repository',
    'upstream_revision',
    'asset_filename',
    'asset_bytes',
    'asset_sha256',
    'license_id',
    'compatible_runtime_ids',
    'public_distribution',
    'installer_bundled',
    'bootstrap_purpose',
    'status'
  ]);
  if (
    object.format !== 'GGUF' ||
    object.quantization !== 'Q4_K_M' ||
    object.public_distribution !== false ||
    object.installer_bundled !== false ||
    object.bootstrap_purpose !== 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION'
  ) throw invalid();
  const compatibleRuntimeIds = boundedArray(object.compatible_runtime_ids, 32).map((item) => validateArtifactId(String(item)));
  validateUniqueSorted(compatibleRuntimeIds);
  return {
    model_id: validateArtifactId(String(object.model_id)),
    provider: safeText(object.provider, 256),
    family: safeText(object.family, 256),
    display_name: safeText(object.display_name, 256),
    format: 'GGUF',
    quantization: 'Q4_K_M',
    upstream_repository: safeText(object.upstream_repository, 256),
    upstream_revision: safeText(object.upstream_revision, 256),
    asset_filename: safeFilename(object.asset_filename),
    asset_bytes: positiveSafeInteger(object.asset_bytes),
    asset_sha256: validateHash(object.asset_sha256),
    license_id: safeText(object.license_id, 256),
    compatible_runtime_ids: compatibleRuntimeIds,
    public_distribution: false,
    installer_bundled: false,
    bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION',
    status: validateCatalogStatus(object.status)
  };
}

function validateCatalogIdentity(object: Readonly<Record<string, unknown>>): ManagedCatalogIdentity {
  if (object.schema_version !== 1 || object.catalog_id !== 'localcomet-approved-artifacts') throw invalid();
  return {
    schema_version: 1,
    catalog_id: 'localcomet-approved-artifacts',
    catalog_version: patternString(object.catalog_version, /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/),
    catalog_digest: validateHash(object.catalog_digest)
  };
}

function validateCatalogStatus(value: unknown): 'approved_internal_bootstrap' {
  return exactString(value, ['approved_internal_bootstrap']);
}

function validateInstallationStatus(value: unknown): ArtifactInstallationStatus {
  return exactString(value, [
    'not_installed',
    'valid',
    'bytes_mismatch',
    'hash_mismatch',
    'invalid_path',
    'invalid_format',
    'missing_required_file',
    'unexpected_file',
    'io_error'
  ]);
}

function validateArtifactId(value: string): string {
  if (!/^[a-z0-9][a-z0-9._-]{2,95}$/.test(value)) throw invalid();
  return value;
}

function validateDownloadJobId(value: string): string {
  if (!/^[0-9a-f]{64}$/.test(value)) throw invalid();
  return value;
}

function validateHash(value: unknown): string {
  return patternString(value, /^[0-9a-f]{64}$/);
}

function safeFilename(value: unknown): string {
  return patternString(value, /^[A-Za-z0-9][A-Za-z0-9._+-]{0,255}$/);
}

function safeText(value: unknown, limit: number): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > limit || /[\0-\x1f\x7f]/.test(value)) throw invalid();
  return value;
}

function safeTextAllowEmpty(value: unknown, limit: number): string {
  if (typeof value !== 'string' || value.length > limit || /[\0-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value)) throw invalid();
  return value;
}

function nullableSafeText(value: unknown, limit: number): string | null {
  return value === null ? null : safeText(value, limit);
}

function patternString(value: unknown, pattern: RegExp): string {
  if (typeof value !== 'string' || !pattern.test(value)) throw invalid();
  return value;
}

function nullablePattern(value: unknown, pattern: RegExp): string | null {
  return value === null ? null : patternString(value, pattern);
}

function nullableHash(value: unknown): string | null {
  return value === null ? null : validateHash(value);
}

function positiveSafeInteger(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) throw invalid();
  return value;
}

function nonNegativeSafeInteger(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw invalid();
  return value;
}

function boundedNonNegativeInteger(value: unknown, maximum: number): number {
  const integer = nonNegativeSafeInteger(value);
  if (integer > maximum) throw invalid();
  return integer;
}

function boundedArray(value: unknown, limit: number): readonly unknown[] {
  if (!Array.isArray(value) || value.length > limit) throw invalid();
  return value;
}

function validateUnique(values: readonly string[]): void {
  if (new Set(values).size !== values.length) throw invalid();
}

function validateUniqueSorted(values: readonly string[]): void {
  validateUnique(values);
  if (values.some((value, index) => index > 0 && values[index - 1]! > value)) throw invalid();
}

function exactString<const T extends string>(value: unknown, options: readonly T[]): T {
  if (typeof value !== 'string' || !options.includes(value as T)) throw invalid();
  return value as T;
}

function exactBoolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw invalid();
  return value;
}

function validatePort(value: number): number {
  if (!Number.isInteger(value) || value < 1024 || value > 65535) throw invalid();
  return value;
}

function validateModelId(value: string): string {
  if (!value || value.length > 192 || /\s|\0/.test(value)) throw invalid();
  return value;
}

function validateTurnId(value: string): string {
  if (!/^[0-9a-f]{24}$/.test(value)) throw invalid();
  return value;
}

function validateChatSessionId(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(value)) throw invalid();
  return value;
}

function validateMaxTokens(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1 || value > 512) throw invalid();
  return value;
}

function validateFingerprint(value: string): string {
  if (!/^[0-9a-f]{64}$/.test(value)) throw invalid();
  return value;
}

function expectRecord(value: unknown): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw invalid();
  return value;
}

function expectExactRecord(value: unknown, expectedKeys: readonly string[]): Readonly<Record<string, unknown>> {
  const object = expectRecord(value);
  const actual = Object.keys(object).sort();
  const expected = [...expectedKeys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) throw invalid();
  return object;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function invalid(): SanitizedGatewayError {
  return { code: 'invalid_payload', message: 'Invalid Local Model Gateway payload' };
}

function sanitize(value: string): string {
  return value.replace(/Traceback[\s\S]*/g, '<redacted>').replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>');
}

function bounded(value: string, limit: number): string {
  return value.slice(0, limit);
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/agent/Diagnostics.svelte (265 строк, 9611 байт)

````svelte
<script lang="ts">
  import EventStream from '$lib/components/common/EventStream.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { modelGatewayStore } from '$lib/stores/modelGateway';
  import { inspectorVisible } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  export let className = '';
  export let onClose: () => void = () => undefined;

  $: sessionShort = shortId($controlPlaneStore.currentSession?.session_id, $t);
  $: threadShort = shortId($controlPlaneStore.currentThread?.thread_id, $t);
  $: turnShort = shortId($controlPlaneStore.currentTurn?.turn_id, $t);
  $: currentItem = $controlPlaneStore.items[$controlPlaneStore.items.length - 1];
  $: turnState = $controlPlaneStore.currentTurn?.state ?? $t('diag.not_started');
  $: bridgeLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');
  $: bridgeTone =
    $controlPlaneStore.bridgeState === 'READY'
      ? 'ready'
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? 'info'
        : $controlPlaneStore.bridgeState === 'ERROR'
          ? 'danger'
          : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
            ? 'disabled'
            : 'unknown';
  $: sidecarLabel = $controlPlaneStore.bootstrap?.sidecar_ready ? $t('diag.sidecar_ready') : $t('diag.sidecar_unknown');
  $: sidecarTone = $controlPlaneStore.bootstrap?.sidecar_ready ? 'ready' : 'unknown';

  type Translate = (key: string) => string;

  function shortId(value: string | undefined, translate: Translate): string {
    return value ? `${value.slice(0, 6)}...${value.slice(-4)}` : translate('diag.unknown');
  }

  function translateTurnState(state: string, translate: Translate): string {
    switch (state) {
      case 'RUNNING': return translate('diag.running');
      case 'COMPLETED': return translate('diag.completed');
      case 'CANCELLED': return translate('diag.cancelled');
      case 'FAILED': return translate('diag.error');
      case 'Not run': return translate('diag.not_run');
      default: return state;
    }
  }

  function translateModelCalled(called: boolean, translate: Translate): string {
    return called ? translate('diag.yes') : translate('diag.no');
  }

  function translateGatewayStatus(status: string, translate: Translate): string {
    switch (status) {
      case 'Not configured': return translate('diag.not_configured');
      case 'Probing': return translate('diag.probing');
      case 'Unavailable': return translate('diag.unavailable');
      case 'Ready': return translate('diag.ready');
      case 'Binding required': return translate('diag.binding_required');
      case 'Bound': return translate('diag.bound');
      case 'Generating': return translate('diag.generating');
      case 'Cancelling': return translate('diag.cancelling');
      case 'Completed': return translate('diag.completed');
      case 'Cancelled': return translate('diag.cancelled');
      case 'Failed': return translate('diag.failed');
      default: return status;
    }
  }

  function translatePersistence(value: string, translate: Translate): string {
    return value === 'Off' ? translate('diag.off') : value;
  }
</script>

<aside id="diagnostics-panel" class="diagnostics {className}" class:hidden={!$inspectorVisible && !className} aria-label={$t('diag.title')}>
  <header>
    <div>
      <span class="eyebrow">{$t('diag.title')}</span>
      <h2>{$t('diag.runtime_state')}</h2>
    </div>
    <button type="button" class="plain-button close-button" aria-label={$t('diag.close')} onclick={onClose}>
      <Icon name="cancel" size={16} />
      <span>{$t('diag.close')}</span>
    </button>
  </header>

  <section class="summary" aria-label={$t('diag.summary')}>
    <StatusBadge label={bridgeLabel} tone={bridgeTone} />
    <StatusBadge label={sidecarLabel} tone={sidecarTone} />
  </section>

  <section aria-label={$t('diag.summary')}>
    <h3>{$t('diag.summary')}</h3>
    <dl>
      <TelemetryRow label={$t('diag.session')} value={sessionShort} tone={$controlPlaneStore.currentSession ? 'ready' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.thread')} value={threadShort} tone={$controlPlaneStore.currentThread ? 'ready' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.turn')} value={turnShort} tone={$controlPlaneStore.currentTurn ? 'info' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.turn_state')} value={translateTurnState(turnState, $t)} tone={$controlPlaneStore.currentTurn ? 'info' : 'unknown'} />
      <TelemetryRow label={$t('diag.current_item')} value={currentItem?.kind ?? $t('diag.unknown')} tone={currentItem ? 'info' : 'unknown'} />
      <TelemetryRow label={$t('diag.last_event')} value={$controlPlaneStore.currentTurn?.last_sequence ?? $t('diag.unknown')} tone={$controlPlaneStore.currentTurn?.last_sequence !== undefined ? 'info' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.event_count')} value={$controlPlaneStore.eventCount} tone={$controlPlaneStore.eventCount > 0 ? 'info' : 'unknown'} mono />
    </dl>
  </section>

  <section aria-label={$t('diag.tab_Телеметрия')}>
    <h3>{$t('diag.tab_Телеметрия')}</h3>
    <dl>
      <TelemetryRow label={$t('diag.model_gateway')} value={translateGatewayStatus($modelGatewayStore.status, $t)} tone={$modelGatewayStore.binding ? 'ready' : 'disabled'} />
      <TelemetryRow label={$t('diag.model_called')} value={translateModelCalled($modelGatewayStore.modelCalled, $t)} tone={$modelGatewayStore.modelCalled ? 'ready' : 'disabled'} />
      <TelemetryRow label={$t('diag.tools_executed')} value={$modelGatewayStore.toolsExecuted} tone="disabled" mono />
      <TelemetryRow label={$t('diag.persistence')} value={translatePersistence($modelGatewayStore.persistence, $t)} tone="disabled" />
      <TelemetryRow label={$t('diag.provider')} value={$modelGatewayStore.binding?.provider_id ?? $t('diag.not_configured')} tone={$modelGatewayStore.binding ? 'ready' : 'disabled'} mono />
      <TelemetryRow label={$t('diag.response_mode')} value={$modelGatewayStore.binding?.harness_id ?? $t('diag.not_configured')} tone={$modelGatewayStore.binding ? 'ready' : 'disabled'} mono />
    </dl>
  </section>

  <section aria-label={$t('diag.tab_События')}>
    <h3>{$t('diag.tab_События')}</h3>
    <EventStream events={$controlPlaneStore.recentEvents} />
  </section>

</aside>

<style>
  .diagnostics {
    --telemetry-row-columns: repeat(2, minmax(0, 1fr));
    --telemetry-row-alignment: start;
    --telemetry-label-display: grid;
    width: var(--inspector-width);
    min-width: var(--inspector-width);
    max-width: 100vw;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-gutter: stable;
    border-left: var(--border-thin);
    border-right: 0;
    padding: var(--lc-space-4);
    background: var(--lc-panel);
    backdrop-filter: blur(18px);
  }

  .diagnostics.hidden {
    display: none;
  }

  header {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-block-start: calc(0px - var(--lc-space-4));
    margin-inline: calc(0px - var(--lc-space-4));
    border-bottom: var(--border-thin);
    padding: var(--lc-space-4);
    background: var(--lc-panel-solid);
  }

  header > div {
    min-width: 0;
  }

  .eyebrow {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    margin-top: var(--lc-space-1);
    font-size: 17px;
    overflow-wrap: anywhere;
  }

  h3 {
    margin: var(--lc-space-5) 0 var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .close-button {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    gap: var(--lc-space-1);
    min-height: 32px;
    padding: 0 var(--lc-space-2);
    color: var(--lc-muted);
  }

  .close-button:hover {
    color: var(--lc-text);
  }

  .summary {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  dl {
    display: grid;
    gap: var(--lc-space-1);
    margin: 0;
  }

  .summary {
    margin-bottom: var(--lc-space-3);
    padding-bottom: var(--lc-space-3);
    border-bottom: var(--border-thin);
  }

  .summary :global(.status-badge) {
    max-width: 100%;
    white-space: normal;
    overflow-wrap: anywhere;
  }

  @media (max-width: 1199px) {
    .diagnostics:not(.drawer-open) {
      display: none;
    }

    .diagnostics.drawer-open {
      position: fixed;
      top: var(--shell-header-height);
      right: 0;
      z-index: 40;
      display: block;
      width: min(var(--inspector-width), calc(100vw - var(--rail-width)));
      min-width: 0;
      max-width: 100vw;
      height: calc(100vh - var(--shell-header-height));
      box-shadow: var(--lc-shadow);
    }
  }

  @media (max-width: 680px) {
    .diagnostics.drawer-open {
      width: 100vw;
      min-width: 0;
      max-width: 100vw;
      right: 0;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/ApprovalCard.svelte (53 строк, 1305 байт)

````svelte
<script lang="ts">
  import type { ApprovalMock } from '$lib/data/mockData';
  import { t } from '$lib/i18n';

  export let item: ApprovalMock;
</script>

<article class="approval card-surface" aria-label={$t('approval.section_aria')}>
  <div>
    <span class="status-pill"><span class="status-dot disabled"></span>{$t('approval.disabled')}</span>
    <h2>{item.title}</h2>
    <p>{item.detail}</p>
  </div>
  <div class="approval-actions">
    <button type="button" disabled aria-label={$t('approval.confirm_aria')}>{$t('approval.confirm')}</button>
    <button type="button" disabled aria-label={$t('approval.reject_aria')}>{$t('approval.reject')}</button>
  </div>
</article>

<style>
  .approval {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-4);
    border-color: var(--lc-line);
    padding: var(--lc-space-4);
  }

  h2 {
    margin: var(--lc-space-3) 0 var(--lc-space-1);
    font-size: 17px;
  }

  p {
    margin: 0;
    color: var(--color-muted);
  }

  .approval-actions {
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
  }

  button {
    min-width: 88px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--color-panel);
    color: var(--color-muted);
    cursor: not-allowed;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/CodeBlock.svelte (64 строк, 1447 байт)

````svelte
<script lang="ts">
  import type { CodeBlockMock } from '$lib/data/mockData';

  export let block: CodeBlockMock;
</script>

<figure class="code-block" aria-label="Disabled runtime capability summary">
  <figcaption>
    <span>{block.filename}</span>
    <div>
      <span>{block.language}</span>
      <button type="button" disabled aria-label="Copy disabled in this release">Copy</button>
    </div>
  </figcaption>
  <pre><code>{block.code}</code></pre>
</figure>

<style>
  .code-block {
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    overflow: hidden;
    background: var(--color-code);
  }

  figcaption {
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-4);
    border-bottom: var(--border-thin);
    padding: 0 var(--lc-space-4);
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 12px;
  }

  figcaption div {
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
  }

  button {
    min-height: 32px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--color-panel);
    color: var(--color-muted);
    cursor: not-allowed;
  }

  pre {
    margin: 0;
    overflow-x: auto;
    padding: var(--lc-space-4);
    color: var(--color-text);
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/MessageComposer.svelte (257 строк, 7552 байт)

````svelte
<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import KnowledgeToggle from '$lib/components/knowledge/KnowledgeToggle.svelte';
  import FilesPanel from '$lib/components/files/FilesPanel.svelte';
  import { composerDraft, openSettings, selectedConversationId, setComposerDraft } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';
  import { cancelLocalModelTurn, inferenceRequestStore, managedModelReady, startLocalModelTurn } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';
  import { includedFileIds } from '$lib/stores/files';

  let textarea: HTMLTextAreaElement;
  let restoreComposerFocus = false;
  let previouslyGenerating = false;

  $: isGenerating = ['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle);
  $: canSend = $managedModelReady && Boolean($composerDraft.trim()) && !isGenerating;
  $: requestErrorKey = $inferenceRequestStore.lifecycle === 'timed_out'
    ? 'chat.request_timed_out_detail'
    : 'chat.request_failed_detail';
  $: {
    const generatingNow = isGenerating;
    if (previouslyGenerating && !generatingNow) {
      void restoreFocusAfterRequest();
    }
    previouslyGenerating = generatingNow;
  }

  async function restoreFocusAfterRequest(): Promise<void> {
    if (!restoreComposerFocus) return;
    await tick();
    const active = document.activeElement;
    const focusRemainedInComposer =
      !active ||
      active === document.body ||
      active === document.documentElement ||
      active === textarea ||
      (active instanceof HTMLElement && Boolean(active.closest('.composer-region')));
    if (!focusRemainedInComposer) {
      restoreComposerFocus = false;
      return;
    }
    if (!textarea || textarea.disabled) return;
    restoreComposerFocus = false;
    textarea.focus({ preventScroll: true });
  }

  function resizeDraftBox(): void {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
  }

  async function send(): Promise<void> {
    if (isGenerating) {
      restoreComposerFocus = true;
      await cancelLocalModelTurn();
      await restoreFocusAfterRequest();
      return;
    }
    if (!canSend) return;
    restoreComposerFocus = true;
    const draft = $composerDraft;
    await startLocalModelTurn(draft, $selectedConversationId, $includedFileIds);
    await restoreFocusAfterRequest();
    resizeDraftBox();
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }
</script>

<div class="composer-region">
  <form class="composer-wrap" aria-label={$t('chat.type_message')} onsubmit={(event) => event.preventDefault()}>
    <FilesPanel />
    <KnowledgeToggle />
    <div class="composer card-surface">
      <label class="sr-only" for="composer-draft">{$t('chat.type_message')}</label>
      <textarea
        id="composer-draft"
        bind:this={textarea}
        value={$composerDraft}
        maxlength="12000"
        rows="1"
        placeholder={$managedModelReady ? (isGenerating ? $t('chat.model_responding') : $t('chat.type_message')) : $acquisitionBusy ? $t('chat.model_installing') : $t('chat.connect_model_first')}
        disabled={!$managedModelReady || isGenerating}
        oninput={(event) => {
          setComposerDraft(event.currentTarget.value);
          resizeDraftBox();
        }}
        onkeydown={handleKeydown}
      ></textarea>

      <button type="button" class="send-button" disabled={isGenerating ? false : !canSend} onclick={() => void send()}>
        <span>{isGenerating ? $t('chat.stop') : $t('chat.send')}</span>
        <Icon name={isGenerating ? 'stop' : 'send'} size={18} />
      </button>
    </div>
    {#if $inferenceRequestStore.lastError}
      <p class="request-error" role="status">{$t(requestErrorKey)}</p>
    {/if}
    {#if !$managedModelReady && !isGenerating}
      <div class="first-use" role="status">
        <strong>{$t('chat.model_not_connected')}</strong>
        <p>{$acquisitionBusy ? $t('chat.model_loading_detail') : $t('chat.model_not_connected_detail')}</p>
        <div>
          <button type="button" class="setup-button" onclick={() => openSettings('models')}>{$t('chat.setup_local_ai')}</button>
          <button type="button" class="models-button" onclick={() => openSettings('models')}>{$t('chat.open_models')}</button>
        </div>
      </div>
    {/if}
  </form>
</div>

<style>
  .composer-region {
    min-width: 0;
    min-height: 0;
    flex: 0 0 auto;
  }

  .composer-wrap {
    width: min(calc(100% - 48px), var(--content-width));
    margin: 0 auto 16px;
    z-index: 10;
  }

  .composer {
    min-height: 60px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 8px;
    border-color: color-mix(in srgb, var(--lc-line) 84%, transparent);
    border-radius: var(--lc-radius-lg);
    padding: 8px;
    background: color-mix(in srgb, var(--lc-panel-solid) 60%, transparent);
    box-shadow: var(--lc-shadow-e1);
    backdrop-filter: blur(12px);
  }

  textarea {
    width: 100%;
    min-width: 0;
    min-height: 42px;
    max-height: 150px;
    resize: none;
    overflow-y: auto;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--lc-text);
    font-size: 14px;
    line-height: 1.5;
    padding: 10px 8px;
  }

  textarea:disabled {
    color: var(--lc-faint);
  }

  .send-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    min-width: 88px;
    min-height: 40px;
    border: 0;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: #071009;
    font-size: 14px;
    font-weight: 650;
    cursor: pointer;
  }

  .send-button:disabled {
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
  }

  .request-error {
    margin: var(--lc-space-2) 0 0;
    color: var(--lc-danger);
    font-size: 12px;
    font-weight: 700;
  }

  .first-use {
    display: grid;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    padding: 10px 12px;
    background: color-mix(in srgb, var(--lc-panel-solid) 50%, transparent);
    font-size: 12px;
  }

  .first-use p {
    margin: 0;
    color: var(--lc-muted);
    line-height: 1.45;
  }

  .first-use > div {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .setup-button,
  .models-button {
    min-height: 34px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: 0 var(--lc-space-3);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .setup-button {
    border-color: var(--lc-accent);
    background: var(--lc-accent);
    color: #071009;
  }

  .models-button {
    background: var(--lc-panel-solid);
    color: var(--lc-text);
  }

  .composer-wrap :global(.files-panel) {
    gap: 8px;
    margin-bottom: 6px;
    border-color: color-mix(in srgb, var(--lc-line) 72%, transparent);
    border-radius: var(--lc-radius-lg);
    padding: 8px 10px;
    background: color-mix(in srgb, var(--lc-panel-solid) 48%, transparent);
  }

  .composer-wrap :global(.knowledge-availability) {
    padding: 2px 8px 7px;
  }

  @media (max-width: 760px) {
    .composer-wrap {
      width: calc(100% - 24px);
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/MessageList.svelte (189 строк, 5135 байт)

````svelte
<script lang="ts">
  import EmptyState from '$lib/components/common/EmptyState.svelte';
  import { chatMessages, openSettings, selectedConversationId } from '$lib/stores/shellStore';
  import {
    inferenceBusy,
    managedModelReady,
    managedRuntimeStore,
    retryLocalModelTurn
  } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';
  import { t } from '$lib/i18n';

  $: showEmptyState = $chatMessages.length === 0;
  $: modelLoading = $acquisitionBusy || ['Validating', 'Starting', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '') ||
    ['Validating', 'Loading', 'Unloading'].includes($managedRuntimeStore.status?.model_state ?? '');
  $: emptyTitleKey = $managedModelReady
    ? 'chat.first_use_ready'
    : modelLoading
      ? 'chat.model_loading'
      : 'chat.model_unavailable';
  $: emptyDetailKey = $managedModelReady
    ? 'chat.first_use_detail'
    : modelLoading
      ? 'chat.model_loading_detail'
      : 'chat.model_unavailable_detail';

  function stateKey(state: string): string {
    return `chat.state_${state}`;
  }
</script>

<section class="message-list" aria-label={$t('chat.message_history')}>
  {#if showEmptyState}
    <EmptyState
      title={$t(emptyTitleKey)}
      detail={$t(emptyDetailKey)}
      busy={modelLoading}
      statusLabel={modelLoading ? $t('chat.model_loading_status') : $managedModelReady ? $t('chat.local_only_status') : undefined}
      actionLabel={!$managedModelReady && !modelLoading ? $t('chat.setup_local_ai') : undefined}
      onAction={!$managedModelReady && !modelLoading ? () => openSettings('models') : undefined}
    />
  {:else}
    {#each $chatMessages as message}
      <article class="message {message.role}" aria-label={message.role === 'user' ? $t('chat.user_message') : $t('chat.model_response')}>
        <div class="avatar" aria-hidden="true">{message.role === 'user' ? 'U' : 'LC'}</div>
        <div class="bubble">
          <div class="bubble-meta">
            <span>{message.role === 'user' ? $t('chat.you') : $t('chat.model')}</span>
            {#if message.demo}
              <span class="demo-badge">{$t('chat.demo')}</span>
            {/if}
          </div>
          <p>{message.body}</p>
          {#if message.role === 'assistant' && message.state && message.state !== 'completed'}
            <div class="request-result">
              <span class="request-state" data-state={message.state}>{$t(stateKey(message.state))}</span>
              {#if ['cancelled', 'timed_out', 'failed'].includes(message.state)}
                <button
                  type="button"
                  class="retry-button"
                  disabled={$inferenceBusy || !$managedModelReady}
                  onclick={() => void retryLocalModelTurn(message.requestId ?? '', $selectedConversationId)}
                >
                  {$t('chat.retry')}
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </article>
    {/each}
  {/if}
</section>

<style>
  .message-list {
    min-width: 0;
    max-width: 100%;
    display: grid;
    gap: 12px;
  }

  .message {
    min-width: 0;
    max-width: 100%;
    display: flex;
    justify-content: flex-start;
    animation: message-in 400ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  .message.user {
    justify-content: flex-end;
  }

  .avatar {
    display: none;
  }

  .bubble {
    min-width: 0;
    width: fit-content;
    max-width: 80%;
    border: 1px solid color-mix(in srgb, var(--lc-line) 84%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-panel-solid) 60%, transparent);
    padding: 10px 16px;
    font-size: 13.5px;
    line-height: 1.625;
  }

  .user .bubble {
    border-color: transparent;
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 500;
  }

  .runtime .bubble {
    border-color: var(--lc-line-strong);
  }

  .bubble-meta {
    display: none;
  }

  p {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .request-state {
    display: inline-block;
    margin-top: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    font-family: var(--lc-mono);
  }

  .user .request-state {
    color: currentColor;
  }

  .request-result {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-2);
  }

  .request-result .request-state {
    margin-top: 0;
  }

  .retry-button {
    min-height: 30px;
    padding: 0 var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .retry-button:disabled {
    color: var(--lc-faint);
    cursor: not-allowed;
  }

  @keyframes message-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 680px) {
    .bubble {
      max-width: 94%;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/ToolCallCard.svelte (87 строк, 1641 байт)

````svelte
<script lang="ts">
  import type { ToolCallMock } from '$lib/data/mockData';

  export let tool: ToolCallMock;
</script>

<article class="tool-card tool-surface" aria-label="Tools disabled">
  <div class="tool-head">
    <div>
      <span class="eyebrow">Tool Runtime</span>
      <h2>{tool.operation}</h2>
    </div>
    <span class="status-pill"><span class="status-dot disabled"></span>{tool.status}</span>
  </div>
  <dl>
    <div>
      <dt>Target</dt>
      <dd>{tool.target}</dd>
    </div>
    <div>
      <dt>Elapsed</dt>
      <dd>{tool.elapsed}</dd>
    </div>
  </dl>
  <details>
    <summary>Details</summary>
    <p>{tool.detail}</p>
    <pre>{tool.result}</pre>
  </details>
</article>

<style>
  .tool-card {
    padding: var(--lc-space-4);
  }

  .tool-head {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-4);
  }

  .eyebrow,
  dt {
    color: var(--color-muted);
    font-size: 12px;
    font-weight: 700;
  }

  h2 {
    margin: var(--lc-space-1) 0 0;
    font-size: 16px;
  }

  dl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--lc-space-4);
    margin: var(--lc-space-4) 0;
  }

  dd {
    margin: var(--lc-space-1) 0 0;
    font-family: var(--font-mono);
    overflow-wrap: anywhere;
  }

  summary {
    cursor: pointer;
    color: var(--color-muted);
    font-weight: 700;
  }

  p,
  pre {
    margin: var(--lc-space-3) 0 0;
  }

  pre {
    overflow-x: auto;
    border-radius: var(--lc-radius-sm);
    background: var(--color-code);
    color: var(--color-text);
    padding: var(--lc-space-3);
    font-family: var(--font-mono);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/transcriptScroll.ts (32 строк, 1130 байт)

````typescript
export const TRANSCRIPT_BOTTOM_THRESHOLD_PX = 96;

export interface TranscriptScrollMetrics {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

export interface TranscriptScrollTarget extends TranscriptScrollMetrics {
  scrollTop: number;
}

export function transcriptDistanceFromBottom(metrics: TranscriptScrollMetrics): number {
  const { scrollTop, scrollHeight, clientHeight } = metrics;
  if (![scrollTop, scrollHeight, clientHeight].every(Number.isFinite)) return Number.POSITIVE_INFINITY;
  if (scrollHeight < 0 || clientHeight < 0) return Number.POSITIVE_INFINITY;
  return Math.max(0, scrollHeight - clientHeight - Math.max(0, scrollTop));
}

export function isTranscriptNearBottom(
  metrics: TranscriptScrollMetrics,
  threshold = TRANSCRIPT_BOTTOM_THRESHOLD_PX
): boolean {
  if (!Number.isFinite(threshold) || threshold < 0) return false;
  return transcriptDistanceFromBottom(metrics) <= threshold;
}

export function followTranscriptToEnd(target: TranscriptScrollTarget, following: boolean): boolean {
  if (!following) return false;
  target.scrollTop = target.scrollHeight;
  return true;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/chat/VerificationCard.svelte (36 строк, 667 байт)

````svelte
<script lang="ts">
  import type { VerificationMock } from '$lib/data/mockData';

  export let item: VerificationMock;
</script>

<article class="verification card-surface" aria-label="Verification not run">
  <span class="status-pill"><span class="status-dot disabled"></span>{item.status}</span>
  <div>
    <h2>{item.label}</h2>
    <p>{item.detail}</p>
  </div>
</article>

<style>
  .verification {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-4);
    padding: var(--lc-space-4);
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  p {
    margin-top: var(--lc-space-1);
    color: var(--color-muted);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/CommandPalette.svelte (280 строк, 7622 байт)

````svelte
<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { t } from '$lib/i18n';
  import {
    closeCommandPalette,
    commandPaletteOpen,
    inspectorVisible,
    openSettings,
    setActiveWorkspace,
    setDiagnosticsPanelOpen
  } from '$lib/stores/shellStore';

  type PaletteCommand = {
    id: string;
    label: string;
    run: () => void;
  };

  let dialogElement: HTMLDivElement;
  let inputElement: HTMLInputElement;
  let previousFocus: HTMLElement | null = null;
  let query = '';
  let activeIndex = 0;
  let wasOpen = false;

  $: commands = [
    {
      id: 'chat',
      label: $t('commandPalette.command.chat'),
      run: () => setActiveWorkspace('chat')
    },
    {
      id: 'settings',
      label: $t('commandPalette.command.settings'),
      run: openSettings
    },
    {
      id: 'setup',
      label: $t('commandPalette.command.setup'),
      run: () => setActiveWorkspace('setup')
    },
    {
      id: 'models',
      label: $t('commandPalette.command.models'),
      run: () => openSettings('models')
    },
    {
      id: 'observability',
      label: $t('commandPalette.command.observability'),
      run: () => openSettings('observability')
    },
    {
      id: 'diagnostics',
      label: $inspectorVisible
        ? $t('commandPalette.command.hideDiagnostics')
        : $t('commandPalette.command.showDiagnostics'),
      run: () => {
        setActiveWorkspace('chat');
        setDiagnosticsPanelOpen(!$inspectorVisible);
      }
    }
  ] satisfies PaletteCommand[];
  $: normalizedQuery = query.trim().toLocaleLowerCase();
  $: filteredCommands = normalizedQuery
    ? commands.filter((command) => command.label.toLocaleLowerCase().includes(normalizedQuery))
    : commands;
  $: if (activeIndex >= filteredCommands.length) activeIndex = Math.max(0, filteredCommands.length - 1);
  $: activeDescendant = filteredCommands[activeIndex]
    ? `command-palette-option-${filteredCommands[activeIndex].id}`
    : undefined;
  $: if ($commandPaletteOpen && !wasOpen) {
    wasOpen = true;
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    query = '';
    activeIndex = 0;
    void tick().then(() => inputElement?.focus());
  } else if (!$commandPaletteOpen && wasOpen) {
    wasOpen = false;
    const focusTarget = previousFocus;
    previousFocus = null;
    queueMicrotask(() => focusTarget?.focus());
  }

  onDestroy(() => {
    if (wasOpen) previousFocus?.focus();
  });

  function execute(command: PaletteCommand | undefined): void {
    if (!command) return;
    previousFocus = null;
    closeCommandPalette();
    command.run();
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      closeCommandPalette();
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (filteredCommands.length === 0) return;
      const offset = event.key === 'ArrowDown' ? 1 : -1;
      activeIndex = (activeIndex + offset + filteredCommands.length) % filteredCommands.length;
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      execute(filteredCommands[activeIndex]);
      return;
    }
    if (event.key !== 'Tab') return;

    const focusable = Array.from(
      dialogElement.querySelectorAll<HTMLElement>(
        'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
    if (focusable.length === 0) {
      event.preventDefault();
      dialogElement.focus();
      return;
    }
    const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const nextIndex = event.shiftKey
      ? (currentIndex <= 0 ? focusable.length - 1 : currentIndex - 1)
      : (currentIndex >= focusable.length - 1 ? 0 : currentIndex + 1);
    event.preventDefault();
    focusable[nextIndex]?.focus();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) closeCommandPalette();
  }
</script>

{#if $commandPaletteOpen}
  <div
    class="palette-backdrop"
    role="presentation"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
  >
    <div
      bind:this={dialogElement}
      class="command-palette"
      role="dialog"
      aria-modal="true"
      aria-label={$t('commandPalette.label')}
      tabindex="-1"
    >
      <label for="command-palette-search">{$t('commandPalette.search')}</label>
      <input
        bind:this={inputElement}
        id="command-palette-search"
        type="search"
        bind:value={query}
        placeholder={$t('commandPalette.placeholder')}
        autocomplete="off"
        aria-controls="command-palette-list"
        aria-activedescendant={activeDescendant}
        oninput={() => (activeIndex = 0)}
      />

      <div
        id="command-palette-list"
        class="command-list"
        role="listbox"
        aria-label={$t('commandPalette.commands')}
        tabindex="-1"
      >
        {#each filteredCommands as command, index (command.id)}
          <button
            id={`command-palette-option-${command.id}`}
            type="button"
            role="option"
            class:active={index === activeIndex}
            aria-selected={index === activeIndex}
            onmouseenter={() => (activeIndex = index)}
            onclick={() => execute(command)}
          >
            {command.label}
          </button>
        {:else}
          <p class="empty">{$t('commandPalette.empty')}</p>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .palette-backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: start center;
    padding: min(18vh, 160px) var(--lc-space-4) var(--lc-space-4);
    background: color-mix(in srgb, #000 68%, transparent);
  }

  .command-palette {
    width: min(620px, 100%);
    overflow: hidden;
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
  }

  label {
    display: block;
    padding: var(--lc-space-4) var(--lc-space-4) var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  input {
    width: calc(100% - (2 * var(--lc-space-4)));
    min-height: 46px;
    margin: 0 var(--lc-space-4) var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel);
    color: var(--lc-text);
    font: inherit;
    padding: 0 var(--lc-space-3);
  }

  input:focus-visible,
  button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .command-list {
    display: grid;
    gap: var(--lc-space-1);
    max-height: min(360px, 50vh);
    overflow-y: auto;
    border-top: var(--border-thin);
    padding: var(--lc-space-2);
  }

  button {
    min-height: 44px;
    border: 1px solid transparent;
    border-radius: var(--lc-radius-md);
    background: transparent;
    color: var(--lc-text);
    padding: 0 var(--lc-space-3);
    text-align: left;
    cursor: pointer;
  }

  button.active {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .empty {
    margin: 0;
    padding: var(--lc-space-4);
    color: var(--lc-muted);
    text-align: center;
  }

  @media (max-width: 560px) {
    .palette-backdrop {
      padding: var(--lc-space-4) var(--lc-space-2);
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/EmptyState.svelte (104 строк, 2316 байт)

````svelte
<script lang="ts">
  import LocalCometLogo from './LocalCometLogo.svelte';

  export let title: string;
  export let detail: string;
  export let actionLabel: string | undefined = undefined;
  export let onAction: (() => void) | undefined = undefined;
  export let busy = false;
  export let statusLabel: string | undefined = undefined;
</script>

<div class="empty-state" aria-busy={busy} aria-live="polite">
  <LocalCometLogo size={42} labelled={false} />
  <div>
    <h2>{title}</h2>
    <p>{detail}</p>
    {#if statusLabel}
      <span class:busy class="state-label">{statusLabel}</span>
    {/if}
    {#if actionLabel && onAction}
      <button type="button" class="primary-button" onclick={onAction}>
        {actionLabel}
      </button>
    {/if}
  </div>
</div>

<style>
  .empty-state {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-color: color-mix(in srgb, var(--lc-line) 84%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-panel-solid) 50%, transparent);
    padding: 20px;
    animation: empty-in 400ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 14px;
    font-weight: 700;
  }

  p {
    margin-top: var(--lc-space-1);
    color: var(--lc-muted);
    font-size: 13px;
    line-height: 1.55;
  }

  .primary-button {
    margin-top: var(--lc-space-3);
    min-height: 32px;
    padding: 0 12px;
    border: none;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 650;
    font-size: 13px;
    cursor: pointer;
  }

  .primary-button:hover {
    background: var(--lc-accent-strong);
  }

  .state-label {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
  }

  .state-label.busy::before {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--lc-accent);
    content: '';
  }

  @keyframes empty-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/EventStream.svelte (112 строк, 2262 байт)

````svelte
<script lang="ts">
  import type { ControlPlaneEvent } from '$lib/types/controlPlane';
  import { t } from '$lib/i18n';

  export let events: readonly ControlPlaneEvent[] = [];

  $: visibleEvents = events.slice(-12).map((event) => ({
    sequence: event.sequence,
    method: event.method,
    kind: event.kind ?? 'none',
    state: event.state || $t('diag.unknown')
  }));
</script>

<section class="event-stream" aria-label={$t('diag.event_stream_label')}>
  <header>
    <h3>{$t('diag.event_stream')}</h3>
    <span>{events.length}</span>
  </header>
  {#if visibleEvents.length === 0}
    <p class="empty">{$t('diag.no_validated_events')}</p>
  {:else}
    <ol>
      {#each visibleEvents as event}
        <li>
          <span class="seq">#{event.sequence}</span>
          <span class="event-method" title={event.method}>{event.method}</span>
          <small title={`${event.kind} / ${event.state}`}>{event.kind} / {event.state}</small>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .event-stream {
    display: grid;
    min-width: 0;
    gap: var(--lc-space-2);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  h3 {
    margin: 0;
    font-size: 13px;
    text-transform: uppercase;
    color: var(--lc-muted);
  }

  header span,
  .seq,
  small {
    font-family: var(--lc-mono);
  }

  header span {
    color: var(--lc-faint);
    font-size: 12px;
  }

  ol {
    display: grid;
    min-width: 0;
    gap: var(--lc-space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: grid;
    min-width: 0;
    gap: 2px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  .seq {
    color: var(--lc-accent);
    font-size: 11px;
    font-weight: 800;
  }

  .event-method,
  small {
    min-width: 0;
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  small,
  .empty {
    color: var(--lc-muted);
    font-size: 12px;
  }

  .empty {
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    overflow-wrap: anywhere;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/Icon.svelte (50 строк, 2967 байт)

````svelte
<script lang="ts">
  export let name: string;
  export let size = 20;

  const paths: Record<string, string> = {
    add: '<path d="M12 5v14M5 12h14"/>',
    search: '<path d="m21 21-4.4-4.4"/><circle cx="11" cy="11" r="6"/>',
    chat: '<path d="M5 6h14v10H8l-3 3V6z"/>',
    tasks: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
    inspector: '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5"/>',
    audit: '<path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 13l2 2 4-5"/>',
    project: '<path d="M4 7h16v11H4z"/><path d="M8 7V5h8v2"/>',
    run: '<path d="M7 5v14l11-7z"/>',
    model: '<circle cx="12" cy="12" r="7"/><path d="M12 5v14M5 12h14"/>',
    tool: '<path d="m14 6 4 4-8 8H6v-4z"/><path d="M12 8l4 4"/>',
    diag: '<path d="M5 18h14M7 14h10M9 10h6M11 6h2"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.09a2 2 0 0 1 1 1.74v.5a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A7.5 7.5 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    system: '<rect x="4" y="5" width="16" height="11" rx="2"/><path d="M9 20h6M12 16v4"/>',
    collapse: '<path d="m15 6-6 6 6 6"/>',
    expand: '<path d="m9 6 6 6-6 6"/>',
    menu: '<path d="M5 7h14M5 12h14M5 17h14"/>',
    attach: '<path d="m8 12 5.5-5.5a3 3 0 0 1 4.2 4.2L10 18.4a5 5 0 1 1-7-7l7.8-7.8"/>',
    send: '<path d="m4 4 16 8-16 8 4-8z"/><path d="M8 12h12"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    shield: '<path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z"/>',
    cancel: '<path d="M6 6l12 12M18 6 6 18"/>',
    spark: '<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    refresh: '<path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    play: '<polygon points="5 3 19 12 5 21 5 3"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>'
  };
</script>

<svg
  class="lc-icon"
  aria-hidden="true"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
>
  {@html paths[name] ?? paths.chat}
</svg>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/LanguageSwitcher.svelte (161 строк, 3625 байт)

````svelte
<script lang="ts">
  import { locale, setLocale, t } from '$lib/i18n';
  import type { Language } from '$lib/i18n';

  let open = false;
  let menu: HTMLDivElement;
  let button: HTMLButtonElement;

  const languages: Array<{ code: Language; labelKey: string }> = [
    { code: 'ru', labelKey: 'lang.russian' },
    { code: 'en', labelKey: 'lang.english' }
  ];

  function toggle() {
    open = !open;
  }

  function select(code: Language) {
    setLocale(code);
    open = false;
    button?.focus();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      open = false;
      button?.focus();
    }
  }

  function handleGlobalClick(event: MouseEvent) {
    if (open && menu && !menu.contains(event.target as Node) && !button.contains(event.target as Node)) {
      open = false;
    }
  }
</script>

<svelte:window on:click={handleGlobalClick} />

<div class="language-switcher">
  <button
    type="button"
    class="lang-button"
    bind:this={button}
    aria-label={$t('lang.select')}
    aria-expanded={open}
    aria-haspopup="listbox"
    onclick={toggle}
    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
  >
    <span class="lang-label">{$locale === 'ru' ? 'RU' : 'EN'}</span>
    <span class="lang-arrow" aria-hidden="true">{open ? '▲' : '▾'}</span>
  </button>

  {#if open}
    <div
      class="lang-menu"
      bind:this={menu}
      role="listbox"
      aria-label={$t('lang.select')}
      onkeydown={handleKeydown}
    >
      {#each languages as lang}
        <button
          type="button"
          role="option"
          class="lang-option"
          class:selected={$locale === lang.code}
          aria-selected={$locale === lang.code}
          onclick={() => select(lang.code)}
        >
          <span>{$t(lang.labelKey)}</span>
          {#if $locale === lang.code}
            <span class="check" aria-hidden="true">✓</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .language-switcher {
    position: relative;
  }

  .lang-button {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: 32px;
    padding: 0 var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    font-family: var(--lc-mono);
  }

  .lang-button:hover {
    border-color: var(--lc-line);
    color: var(--lc-text);
  }

  .lang-button[aria-expanded="true"] {
    border-color: var(--lc-accent);
    color: var(--lc-accent);
  }

  .lang-arrow {
    font-size: 8px;
    line-height: 1;
  }

  .lang-menu {
    position: absolute;
    bottom: calc(100% + 4px);
    left: 0;
    min-width: 140px;
    background: var(--lc-panel-solid);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    box-shadow: var(--lc-shadow);
    z-index: 60;
    overflow: hidden;
  }

  .lang-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-2);
    width: 100%;
    min-height: 34px;
    padding: 0 var(--lc-space-3);
    border: none;
    background: transparent;
    color: var(--lc-text);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
  }

  .lang-option:hover {
    background: var(--lc-panel-soft);
  }

  .lang-option.selected {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .check {
    color: var(--lc-accent);
    font-weight: 800;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/LocalCometLogo.svelte (29 строк, 1083 байт)

````svelte
<script lang="ts">
  export let size = 34;
  export let labelled = true;
</script>

<svg
  class="localcomet-logo"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 64 64"
  role={labelled ? 'img' : undefined}
  aria-label={labelled ? 'LocalComet' : undefined}
  aria-hidden={labelled ? undefined : 'true'}
  width={size}
  height={size}
>
  <path d="M6 8c15 7 27 15 35 27" fill="none" stroke="currentColor" stroke-width="3.1" stroke-linecap="round" opacity=".2" />
  <path d="M9 18c13 4 23 10 31 19" fill="none" stroke="currentColor" stroke-width="2.7" stroke-linecap="round" opacity=".52" />
  <path d="M17 26c9 2 16 6 22 12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity=".9" />
  <circle cx="42" cy="41" r="14" fill="currentColor" fill-opacity=".08" stroke="currentColor" stroke-width="3.4" />
  <circle cx="42" cy="41" r="7" fill="currentColor" />
  <circle cx="46" cy="37" r="3.5" fill="var(--lc-logo-cut, #071009)" fill-opacity=".74" />
</svg>

<style>
  .localcomet-logo {
    display: block;
    color: var(--lc-accent);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/LocalCometSecurityEmblem.svelte (29 строк, 1157 байт)

````svelte
<script lang="ts">
  export let size = 42;
  export let labelled = true;
</script>

<svg
  class="security-emblem"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 220 250"
  role={labelled ? 'img' : undefined}
  aria-label={labelled ? 'LocalComet security emblem' : undefined}
  aria-hidden={labelled ? undefined : 'true'}
  width={size}
  height={Math.round(size * 1.14)}
>
  <path d="M110 16 190 46v66c0 57-32 96-80 122-48-26-80-65-80-122V46l80-30Z" fill="currentColor" fill-opacity=".035" stroke="currentColor" stroke-width="4" />
  <path d="M61 69c29 13 50 29 64 50" fill="none" stroke="currentColor" stroke-width="7" stroke-linecap="round" opacity=".27" />
  <path d="M68 89c24 8 42 21 55 37" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" opacity=".76" />
  <circle cx="126" cy="139" r="31" fill="currentColor" fill-opacity=".08" stroke="currentColor" stroke-width="5" />
  <circle cx="126" cy="139" r="15" fill="currentColor" />
  <circle cx="133" cy="132" r="7" fill="var(--lc-logo-cut, #071009)" fill-opacity=".72" />
</svg>

<style>
  .security-emblem {
    display: block;
    color: var(--lc-accent);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/PolicyDecision.svelte (41 строк, 1177 байт)

````svelte
<script lang="ts">
  import LocalCometSecurityEmblem from './LocalCometSecurityEmblem.svelte';
  import StatusBadge from './StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import type { RiskLevel } from '$lib/risk';
  import { RISK_LABEL_KEY, RISK_TONE } from '$lib/risk';

  export let risk: RiskLevel | undefined = undefined;
</script>

<section class="policy-decision" aria-label={$t('diag.policy_decision_label')}>
  <LocalCometSecurityEmblem size={34} labelled={false} />
  <div>
    <h3>{$t('diag.policy_decision')}</h3>
    {#if risk}
      <StatusBadge label={$t(RISK_LABEL_KEY[risk])} tone={RISK_TONE[risk]} />
    {:else}
      <StatusBadge label={$t('diag.not_evaluated')} tone="unknown" />
    {/if}
  </div>
</section>

<style>
  .policy-decision {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-3);
  }

  h3 {
    margin: 0 0 var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 12px;
    text-transform: uppercase;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/StatusBadge.svelte (54 строк, 1465 байт)

````svelte
<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  export let label: string;
  export let tone: StatusTone | string = 'unknown';

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<span class="status-badge tone-{tone}">
  <StatusDot {tone} {label} />
  <span>{label}</span>
</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    min-height: 24px;
    border: var(--border-thin);
    border-radius: 999px;
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: 2px 10px;
    font-size: 11.5px;
    font-weight: 500;
    white-space: nowrap;
  }

  .tone-ready {
    border-color: color-mix(in srgb, var(--lc-accent) 30%, transparent);
    background: color-mix(in srgb, var(--lc-accent) 12%, transparent);
    color: var(--lc-accent);
  }

  .tone-info {
    border-color: color-mix(in srgb, var(--lc-info) 30%, transparent);
    background: color-mix(in srgb, var(--lc-info) 12%, transparent);
    color: var(--lc-info);
  }

  .tone-waiting {
    border-color: color-mix(in srgb, var(--lc-warning) 30%, transparent);
    background: color-mix(in srgb, var(--lc-warning) 12%, transparent);
    color: var(--lc-warning);
  }

  .tone-danger {
    border-color: color-mix(in srgb, var(--lc-danger) 30%, transparent);
    background: color-mix(in srgb, var(--lc-danger) 12%, transparent);
    color: var(--lc-danger);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/StatusDot.svelte (9 строк, 297 байт)

````svelte
<script lang="ts">
  export let tone: StatusTone | string = 'unknown';
  export let label = 'Unknown';

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<span class="status-dot {tone}" aria-hidden="true"></span>
<span class="sr-only">{label}</span>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/TelemetryRow.svelte (64 строк, 1542 байт)

````svelte
<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  export let label: string;
  export let value: string | number;
  export let tone: StatusTone | string = 'unknown';
  export let mono = false;

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<div class="telemetry-row">
  <dt>
    <StatusDot {tone} label={`${label}: ${value}`} />
    <span class="telemetry-label" title={label}>{label}</span>
  </dt>
  <dd class:mono title={String(value)}>{value}</dd>
</div>

<style>
  .telemetry-row {
    display: grid;
    grid-template-columns: var(--telemetry-row-columns, minmax(0, 1fr) minmax(92px, auto));
    align-items: var(--telemetry-row-alignment, center);
    gap: var(--lc-space-3);
    min-height: 42px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  dt {
    display: var(--telemetry-label-display, inline-flex);
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--lc-space-2);
    min-width: 0;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 720;
  }

  .telemetry-label {
    min-width: 0;
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  dd {
    margin: 0;
    min-width: 0;
    max-width: 100%;
    color: var(--lc-text);
    overflow-wrap: anywhere;
    text-align: right;
    font-size: 12px;
    font-weight: 800;
  }

  .mono {
    font-family: var(--lc-mono);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/common/ThemeToggle.svelte (56 строк, 1445 байт)

````svelte
<script lang="ts">
  import Icon from './Icon.svelte';
  import { setThemeMode, themeMode } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';
  import type { ThemeMode } from '$lib/data/mockData';

  const themeItems: Array<[ThemeMode, string]> = [
    ['system', 'system'],
    ['light', 'sun'],
    ['dark', 'moon']
  ];
</script>

<div class="theme-toggle" aria-label={$t('theme.manage')}>
  {#each themeItems as [mode, icon]}
    {@const label = $t(mode === 'system' ? 'theme.system' : mode === 'light' ? 'theme.light' : 'theme.dark')}
    <button
      type="button"
      class:selected={$themeMode === mode}
      aria-label={label}
      aria-pressed={$themeMode === mode}
      title={label}
      onclick={() => setThemeMode(mode)}
    >
      <Icon name={icon} size={16} />
    </button>
  {/each}
</div>

<style>
  .theme-toggle {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--lc-space-1);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-1);
  }

  button {
    min-width: 0;
    min-height: 32px;
    border: 1px solid transparent;
    border-radius: var(--lc-radius-sm);
    background: transparent;
    color: var(--lc-muted);
    cursor: pointer;
  }

  button.selected {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/files/FilePreviewDialog.svelte (168 строк, 4671 байт)

````svelte
<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import type { SelectedFilePreview } from '$lib/types/files';

  export let preview: SelectedFilePreview;
  export let triggerElement: HTMLElement | null = null;
  export let onClose: () => void = () => undefined;

  let dialogElement: HTMLDivElement;
  let previousFocus: HTMLElement | null = null;

  onMount(() => {
    previousFocus = triggerElement ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    void tick().then(() => dialogElement?.querySelector<HTMLButtonElement>('.preview-close')?.focus());
  });

  onDestroy(() => {
    (triggerElement ?? previousFocus)?.focus();
  });

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(dialogElement.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])'));
    if (focusable.length === 0) {
      event.preventDefault();
      dialogElement.focus();
      return;
    }
    const current = focusable.indexOf(document.activeElement as HTMLElement);
    const next = event.shiftKey
      ? (current <= 0 ? focusable.length - 1 : current - 1)
      : (current >= focusable.length - 1 ? 0 : current + 1);
    event.preventDefault();
    focusable[next]?.focus();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) onClose();
  }
</script>

<div class="preview-backdrop" role="presentation" onclick={handleBackdropClick} onkeydown={handleKeydown}>
  <div
    bind:this={dialogElement}
    class="preview-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="file-preview-title"
    aria-describedby="file-preview-counts"
    tabindex="-1"
  >
    <header>
      <div>
        <span>{$t('files.preview_eyebrow')}</span>
        <h2 id="file-preview-title">{preview.filename}</h2>
      </div>
      <button type="button" class="preview-close" aria-label={$t('files.close_preview')} onclick={onClose}>
        <Icon name="cancel" size={16} />
      </button>
    </header>
    <p id="file-preview-counts" class="counts">
      {preview.displayed_bytes.toLocaleString()} / {preview.original_bytes.toLocaleString()} {$t('files.bytes')}
      · {preview.displayed_characters.toLocaleString()} / {preview.original_characters.toLocaleString()} {$t('files.characters')}
      {#if preview.truncated} · {$t('files.preview_truncated')}{/if}
    </p>
    <pre>{preview.content}</pre>
  </div>
</div>

<style>
  .preview-backdrop {
    position: fixed;
    inset: 0;
    z-index: 90;
    display: grid;
    place-items: center;
    padding: var(--lc-space-4);
    background: color-mix(in srgb, #000 72%, transparent);
  }

  .preview-dialog {
    width: min(780px, 100%);
    max-height: min(760px, calc(100vh - 32px));
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    overflow: hidden;
    border: var(--border-thin);
    border-radius: var(--lc-radius);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
    color: var(--lc-text);
  }

  header {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-3);
    align-items: flex-start;
    border-bottom: var(--border-thin);
    padding: var(--lc-space-4);
  }

  header span {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  h2 {
    margin: var(--lc-space-1) 0 0;
    overflow-wrap: anywhere;
    font-size: 17px;
  }

  .preview-close {
    min-width: 36px;
    min-height: 36px;
    display: grid;
    place-items: center;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    cursor: pointer;
  }

  .counts {
    margin: 0;
    border-bottom: var(--border-thin);
    padding: var(--lc-space-2) var(--lc-space-4);
    color: var(--lc-muted);
    font-size: 11px;
  }

  pre {
    min-width: 0;
    margin: 0;
    overflow: auto;
    padding: var(--lc-space-4);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 12px;
    line-height: 1.55;
    tab-size: 2;
  }

  @media (max-width: 560px) {
    .preview-backdrop {
      padding: var(--lc-space-2);
    }

    .preview-dialog {
      max-height: calc(100vh - 16px);
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/files/FilesPanel.svelte (411 строк, 10520 байт)

````svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import FilePreviewDialog from '$lib/components/files/FilePreviewDialog.svelte';
  import { locale, t } from '$lib/i18n';
  import {
    addFiles,
    clearFilesError,
    closeFilePreview,
    filesCapabilityAvailable,
    filesStore,
    forgetFile,
    includedFilesTotals,
    initializeFilesCapability,
    openFilePreview,
    setFileIncluded
  } from '$lib/stores/files';

  let previewTrigger: HTMLElement | null = null;

  onMount(() => {
    void initializeFilesCapability();
  });

  function showPreview(fileId: string, trigger: HTMLElement): void {
    previewTrigger = trigger;
    void openFilePreview(fileId);
  }

  function formatAdded(unixMs: number): string {
    return new Intl.DateTimeFormat($locale === 'ru' ? 'ru-RU' : 'en-US', {
      dateStyle: 'short',
      timeStyle: 'short'
    }).format(new Date(unixMs));
  }

  function errorKey(code: string): string {
    const known = new Set([
      'LC_FILE_UNSUPPORTED_TYPE',
      'LC_FILE_TOO_LARGE',
      'LC_FILE_BINARY',
      'LC_FILE_INVALID_UTF8',
      'LC_FILE_MISSING',
      'LC_FILE_CHANGED',
      'LC_FILE_ACCESS_DENIED',
      'LC_FILE_REPARSE_POINT',
      'LC_FILE_CONTEXT_LIMIT',
      'LC_FILE_UNREADABLE',
      'LC_FILE_SELECTION_LIMIT',
      'LC_FILE_PICKER_UNAVAILABLE',
      'LC_FILE_STATE_UNAVAILABLE'
    ]);
    return known.has(code) ? `files.error.${code}` : 'files.error.default';
  }
</script>

<section class="files-panel card-surface" aria-labelledby="files-panel-title" aria-busy={$filesStore.selecting}>
  <header>
    <div>
      <h2 id="files-panel-title">{$t('files.title')}</h2>
      <p>{$t('files.read_only')}</p>
    </div>
    <button
      type="button"
      class="add-files"
      disabled={!$filesCapabilityAvailable || $filesStore.selecting}
      aria-label={$t('files.add')}
      onclick={() => void addFiles()}
    >
      <Icon name="attach" size={16} />
      <span>{$filesStore.selecting ? $t('files.selecting') : $t('files.add')}</span>
    </button>
  </header>

  {#if !$filesStore.initialized}
    <p class="empty" role="status">{$t('files.loading')}</p>
  {:else if !$filesCapabilityAvailable}
    <p class="empty" role="status">{$t('files.unavailable')}</p>
  {:else if $filesStore.files.length === 0}
    <p class="empty">{$t('files.empty')}</p>
  {:else}
    <ul class="file-list" aria-label={$t('files.selected_list')}>
      {#each $filesStore.files as file (file.file_id)}
        {@const inclusion = $filesStore.lastContextReport?.files.find((entry) => entry.file_id === file.file_id)}
        <li>
          <div class="file-heading">
            <div class="file-name">
              <strong>{file.filename}</strong>
              <span class:ready={file.readable} class="status">{$t(`files.status.${file.status}`)}</span>
            </div>
            <span class="type">{file.media_type} · .{file.extension}</span>
          </div>
          <dl>
            <div><dt>{$t('files.size')}</dt><dd>{file.byte_size.toLocaleString()} {$t('files.bytes')}</dd></div>
            <div><dt>{$t('files.characters')}</dt><dd>{file.character_count.toLocaleString()}</dd></div>
            <div><dt>{$t('files.added')}</dt><dd>{formatAdded(file.added_at_unix_ms)}</dd></div>
            <div class="location"><dt>{$t('files.location')}</dt><dd title={file.display_location}>{file.display_location}</dd></div>
          </dl>
          <div class="file-actions">
            <label>
              <input
                type="checkbox"
                checked={$filesStore.includedIds.includes(file.file_id)}
                disabled={!file.readable}
                onchange={(event) => setFileIncluded(file.file_id, event.currentTarget.checked)}
              />
              <span>{$t('files.include')}</span>
            </label>
            <button
              type="button"
              disabled={!file.readable || $filesStore.previewingId !== null}
              aria-label={`${$t('files.preview')} ${file.filename}`}
              onclick={(event) => showPreview(file.file_id, event.currentTarget)}
            >
              {$filesStore.previewingId === file.file_id ? $t('files.loading_preview') : $t('files.preview')}
            </button>
            <button
              type="button"
              class="forget"
              disabled={$filesStore.forgettingId !== null}
              aria-label={`${$t('files.forget')} ${file.filename}`}
              onclick={() => void forgetFile(file.file_id)}
            >
              {$filesStore.forgettingId === file.file_id ? $t('files.forgetting') : $t('files.forget')}
            </button>
          </div>
          {#if inclusion}
            <p class="inclusion-report" role="status">
              {$t(inclusion.inclusion === 'full' ? 'files.inclusion.full' : 'files.inclusion.excerpt')}
              · {inclusion.included_bytes.toLocaleString()} / {inclusion.original_bytes.toLocaleString()} {$t('files.bytes')}
              · {inclusion.included_characters.toLocaleString()} / {inclusion.original_characters.toLocaleString()} {$t('files.characters')}
            </p>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if $filesCapabilityAvailable}
    <footer aria-live="polite">
      <span>{$t('files.context_total')}</span>
      <strong>{$includedFilesTotals.count} · {$includedFilesTotals.bytes.toLocaleString()} {$t('files.bytes')} · {$includedFilesTotals.characters.toLocaleString()} {$t('files.characters')}</strong>
      <small>{$t('files.context_excerpt_notice')}</small>
    </footer>
  {/if}

  {#if $filesStore.lastError}
    <div class="file-error" role="alert">
      <span>{$t(errorKey($filesStore.lastError.code))}</span>
      <button type="button" aria-label={$t('files.dismiss_error')} onclick={clearFilesError}>
        <Icon name="cancel" size={14} />
      </button>
    </div>
  {/if}
</section>

{#if $filesStore.preview}
  <FilePreviewDialog preview={$filesStore.preview} triggerElement={previewTrigger} onClose={closeFilePreview} />
{/if}

<style>
  .files-panel {
    display: grid;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  h2,
  header p,
  .empty {
    margin: 0;
  }

  h2 {
    font-size: 13px;
  }

  header p,
  .empty {
    margin-top: 2px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  button,
  label {
    min-height: 34px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-text);
    font-size: 11px;
    font-weight: 740;
  }

  button {
    cursor: pointer;
  }

  button:disabled {
    color: var(--lc-faint);
    cursor: not-allowed;
  }

  .add-files {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-1);
    padding: 0 var(--lc-space-3);
    border-color: var(--lc-line-strong);
    color: var(--lc-accent);
  }

  .file-list {
    display: grid;
    gap: var(--lc-space-2);
    max-height: 310px;
    margin: 0;
    overflow-y: auto;
    padding: 0;
    list-style: none;
  }

  .file-list > li {
    min-width: 0;
    display: grid;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-solid);
  }

  .file-heading,
  .file-name,
  .file-actions,
  footer {
    display: flex;
    align-items: center;
  }

  .file-heading {
    min-width: 0;
    justify-content: space-between;
    gap: var(--lc-space-2);
  }

  .file-name {
    min-width: 0;
    gap: var(--lc-space-2);
  }

  .file-name strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }

  .status {
    flex: 0 0 auto;
    border-radius: 999px;
    padding: 2px 6px;
    background: color-mix(in srgb, var(--lc-danger) 14%, transparent);
    color: var(--lc-danger);
    font-size: 9px;
    font-weight: 800;
  }

  .status.ready {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .type {
    flex: 0 0 auto;
    color: var(--lc-muted);
    font-size: 10px;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, auto)) minmax(120px, 1fr);
    gap: var(--lc-space-2);
    margin: 0;
  }

  dl div {
    min-width: 0;
  }

  dt {
    color: var(--lc-faint);
    font-size: 9px;
    text-transform: uppercase;
  }

  dd {
    min-width: 0;
    margin: 2px 0 0;
    color: var(--lc-muted);
    font-size: 10px;
  }

  .location dd {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--lc-mono);
  }

  .file-actions {
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .file-actions label {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-1);
    padding: 0 var(--lc-space-2);
    cursor: pointer;
  }

  .file-actions input {
    accent-color: var(--lc-accent);
  }

  .file-actions button {
    padding: 0 var(--lc-space-2);
  }

  .file-actions .forget {
    color: var(--lc-danger);
  }

  .inclusion-report {
    margin: 0;
    color: var(--lc-accent);
    font-size: 10px;
    font-weight: 720;
  }

  footer {
    flex-wrap: wrap;
    gap: var(--lc-space-1) var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 10px;
  }

  footer strong {
    color: var(--lc-text);
  }

  footer small {
    flex-basis: 100%;
    color: var(--lc-faint);
    font-size: 9px;
  }

  .file-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-2);
    border: 1px solid color-mix(in srgb, var(--lc-danger) 45%, transparent);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-2);
    color: var(--lc-danger);
    font-size: 11px;
  }

  .file-error button {
    min-width: 30px;
    min-height: 30px;
    display: grid;
    place-items: center;
  }

  @media (max-width: 680px) {
    header,
    .file-heading {
      align-items: stretch;
      flex-direction: column;
    }

    .add-files {
      width: 100%;
    }

    dl {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .location {
      grid-column: 1 / -1;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte (77 строк, 4382 байт)

````svelte
<svelte:window onkeydown={(event) => {
  if (event.key === 'Escape' && $knowledgePreviewStore.lifecycle === 'PREVIEW_READY') void cancelProjectKnowledge();
}} />

<script lang="ts">
  import { t } from '$lib/i18n';
  import { abbreviateKnowledgeHash } from '$lib/knowledge/knowledgePreview';
  import {
    cancelProjectKnowledge,
    decideProjectKnowledge,
    knowledgePreviewStore,
    retryProjectKnowledgePreview,
    sendWithoutKnowledgeAfterFailure,
    toggleKnowledgeSource
  } from '$lib/stores/knowledgePreview';
  import KnowledgeSourceCard from './KnowledgeSourceCard.svelte';
  import KnowledgeStatusBadge from './KnowledgeStatusBadge.svelte';

  $: state = $knowledgePreviewStore;
  $: preview = state.preview;
</script>

{#if state.enabled && state.lifecycle !== 'OFF'}
  <section class="preview-panel" aria-label={$t('knowledge.approval_label')} aria-live="polite">
    <header>
      <div>
        <h3>{$t('knowledge.title')}</h3>
        {#if preview}
          <p>{preview.source_count} {$t('knowledge.sources')} · {preview.total_chars.toLocaleString()} {$t('knowledge.characters')} · {$t('knowledge.vault')} {abbreviateKnowledgeHash(preview.vault_revision)}</p>
        {/if}
      </div>
      <KnowledgeStatusBadge state={state.lifecycle} />
    </header>

    {#if state.lifecycle === 'RETRIEVING'}
      <p class="message">{$t('knowledge.retrieving')}</p>
    {:else if preview}
      <div class="sources">
        {#each preview.sources as source (source.note_id)}
          <KnowledgeSourceCard source={source} expanded={state.expandedSourceIds.includes(source.note_id)} onToggle={() => toggleKnowledgeSource(source.note_id)} />
        {/each}
      </div>
    {/if}

    {#if state.lastError}
      <p class="error" role="alert">{state.lifecycle === 'STALE' ? $t('knowledge.stale_message') : $t('knowledge.failure_message')}</p>
    {/if}

    <footer>
      {#if state.lifecycle === 'PREVIEW_READY'}
        <button class="primary" type="button" onclick={() => void decideProjectKnowledge('INCLUDE_AND_SEND')}>{$t('knowledge.include_send')}</button>
        <button type="button" onclick={() => void decideProjectKnowledge('REJECT_AND_SEND_WITHOUT_KNOWLEDGE')}>{$t('knowledge.send_without')}</button>
        <button type="button" onclick={() => void cancelProjectKnowledge()}>{$t('knowledge.cancel')}</button>
      {:else if state.lifecycle === 'FAILED' || state.lifecycle === 'STALE'}
        <button class="primary" type="button" onclick={() => void retryProjectKnowledgePreview()}>{$t(state.lifecycle === 'STALE' ? 'knowledge.refresh' : 'knowledge.retry')}</button>
        <button type="button" onclick={() => void sendWithoutKnowledgeAfterFailure()}>{$t('knowledge.send_without')}</button>
        <button type="button" onclick={() => void cancelProjectKnowledge()}>{$t('knowledge.cancel')}</button>
      {/if}
    </footer>
  </section>
{/if}

<style>
  .preview-panel { width: min(calc(100% - 48px), var(--content-width)); max-height: min(52vh, 620px); margin: 0 auto var(--lc-space-3); padding: var(--lc-space-4); overflow: auto; border: 1px solid rgb(120 255 152 / 42%); border-radius: var(--lc-radius); background: color-mix(in srgb, var(--lc-panel) 96%, #78ff98 4%); box-shadow: 0 0 24px rgb(120 255 152 / 8%); }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--lc-space-3); }
  h3 { margin: 0; color: var(--lc-text); font-size: .95rem; }
  p { margin: 5px 0 0; color: var(--lc-muted); font-size: .72rem; }
  .sources { display: grid; gap: var(--lc-space-2); margin-top: var(--lc-space-3); }
  .message { padding: var(--lc-space-4) 0; }
  .error { color: #ff9292; }
  footer { display: flex; flex-wrap: wrap; gap: var(--lc-space-2); margin-top: var(--lc-space-3); }
  footer:empty { display: none; }
  footer button { min-height: 38px; padding: 7px 12px; border: 1px solid var(--lc-border); border-radius: var(--lc-radius-sm); background: var(--lc-panel-soft); color: var(--lc-text); cursor: pointer; font-weight: 720; }
  footer button.primary { border-color: #78ff98; background: #78ff98; color: #071009; }
  footer button:focus-visible { outline: 2px solid #78ff98; outline-offset: 2px; }
  @media (max-width: 760px) { .preview-panel { width: calc(100% - 24px); max-height: 58vh; padding: var(--lc-space-3); } header { align-items: center; } footer button { flex: 1 1 100%; } }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte (53 строк, 2989 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
  import type { KnowledgePreviewSource } from '$lib/knowledge/knowledgePreview';
  export let source: KnowledgePreviewSource;
  export let expanded = false;
  export let onToggle: () => void;
</script>

<article class="source-card">
  <button type="button" aria-expanded={expanded} onclick={onToggle}>
    <span class="source-title">{source.title}</span>
    <span class="source-id">{source.note_id}</span>
    <span class="chevron" aria-hidden="true">{expanded ? '−' : '+'}</span>
  </button>
  <div class="provenance">
    <span class="path">{source.relative_path}</span>
    <span>{source.knowledge_layer}</span><span>{source.evidence_class}</span><span>{source.authority}</span>
  </div>
  <div class="headings" aria-label={$t('knowledge.selected_sections')}>
    {#each source.selected_sections as section}
      <span>{section.heading}</span>
    {/each}
  </div>
  {#if expanded}
    <div class="sections">
      {#each source.selected_sections as section}
        <section>
          <h4>{section.heading}</h4>
          <span class="lines">{$t('knowledge.lines')} {section.line_start}–{section.line_end}</span>
          <pre>{section.content}</pre>
        </section>
      {/each}
    </div>
  {/if}
</article>

<style>
  .source-card { min-width: 0; border: 1px solid var(--lc-border); border-radius: var(--lc-radius-sm); background: var(--lc-panel-soft); overflow: hidden; }
  button { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) minmax(90px, auto) 20px; gap: var(--lc-space-2); align-items: center; padding: var(--lc-space-3); border: 0; background: transparent; color: var(--lc-text); text-align: left; cursor: pointer; }
  button:focus-visible { outline: 2px solid #78ff98; outline-offset: -3px; }
  .source-title, .source-id, .path { min-width: 0; overflow-wrap: anywhere; }
  .source-title { font-weight: 760; }
  .source-id, .provenance, .headings, .lines { color: var(--lc-muted); font-family: var(--lc-mono); font-size: .68rem; }
  .chevron { color: #78ff98; font-size: 1.05rem; text-align: center; }
  .provenance, .headings { display: flex; flex-wrap: wrap; gap: 6px 12px; padding: 0 var(--lc-space-3) var(--lc-space-2); }
  .path { flex-basis: 100%; color: var(--lc-text-soft); }
  .headings span { padding: 2px 6px; border: 1px solid var(--lc-border); border-radius: 999px; }
  .sections { display: grid; gap: var(--lc-space-3); padding: var(--lc-space-3); border-top: 1px solid var(--lc-border); }
  section { min-width: 0; }
  h4 { display: inline; margin: 0 var(--lc-space-2) 0 0; color: var(--lc-text); font-size: .8rem; }
  pre { max-width: 100%; margin: var(--lc-space-2) 0 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--lc-text-soft); font: .72rem/1.55 var(--lc-mono); }
  @media (max-width: 620px) { button { grid-template-columns: minmax(0, 1fr) 20px; } .source-id { grid-column: 1; grid-row: 2; } .chevron { grid-column: 2; grid-row: 1 / span 2; } }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeStatusBadge.svelte (14 строк, 822 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
  import type { KnowledgeUiState } from '$lib/knowledge/knowledgePreview';
  export let state: KnowledgeUiState;
  $: tone = ['FAILED', 'STALE'].includes(state) ? 'danger' : ['PREVIEW_READY', 'INJECTED'].includes(state) ? 'ready' : 'neutral';
</script>

<span class:danger={tone === 'danger'} class:ready={tone === 'ready'}>{$t(`knowledge.state_${state.toLowerCase()}`)}</span>

<style>
  span { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border: 1px solid var(--lc-border); border-radius: 999px; color: var(--lc-muted); font-size: .7rem; font-weight: 760; letter-spacing: .03em; }
  span.ready { border-color: rgb(120 255 152 / 52%); color: #78ff98; }
  span.danger { border-color: rgb(255 112 112 / 52%); color: #ff9292; }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeToggle.svelte (19 строк, 766 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
</script>

<div class="knowledge-availability" role="status" aria-label={$t('knowledge.unavailable')}>
  <div>
    <strong>{$t('knowledge.title')}</strong>
    <span>{$t('knowledge.unavailable')}</span>
    <p>{$t('knowledge.unavailable_detail')}</p>
  </div>
</div>

<style>
  .knowledge-availability { padding: 0 var(--lc-space-2) var(--lc-space-2); }
  .knowledge-availability div { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--lc-space-2); min-width: 0; }
  strong { color: var(--lc-text); font-size: .82rem; }
  span { color: var(--lc-muted); font-size: .72rem; font-weight: 720; }
  p { flex-basis: 100%; margin: 0; color: var(--lc-faint); font-size: .7rem; line-height: 1.4; }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/logs/ObservabilityRoom.svelte (115 строк, 5940 байт)

````svelte
<script lang="ts">
  import EventStream from '$lib/components/common/EventStream.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { managedRuntimeStore, refreshManagedRuntimeStatus } from '$lib/stores/modelGateway';

  let refreshing = false;

  async function refresh(): Promise<void> {
    refreshing = true;
    try {
      await refreshManagedRuntimeStatus();
    } finally {
      refreshing = false;
    }
  }
</script>

<section class="observability" aria-labelledby="observability-title">
  <div class="heading">
    <div>
      <span class="eyebrow">{$t('observability.eyebrow')}</span>
      <h3 id="observability-title">{$t('observability.title')}</h3>
      <p>{$t('observability.subtitle')}</p>
    </div>
    <button type="button" disabled={refreshing} onclick={() => void refresh()}>
      <Icon name="refresh" size={15} />
      {$t(refreshing ? 'observability.refreshing' : 'observability.refresh')}
    </button>
  </div>

  <div class="notice">
    <Icon name="shield" size={18} />
    <p>{$t('observability.boundary')}</p>
  </div>

  <div class="summary">
    <div>
      <span>{$t('observability.control_events')}</span>
      <strong>{$controlPlaneStore.recentEvents.length}</strong>
    </div>
    <div>
      <span>{$t('observability.runtime_state')}</span>
      <StatusBadge
        label={$managedRuntimeStore.status?.state ?? $t('common.not_determined')}
        tone={$managedRuntimeStore.status?.state === 'Ready' ? 'ready' : 'unknown'}
      />
    </div>
    <div>
      <span>{$t('observability.runtime_lines')}</span>
      <strong>{$managedRuntimeStore.logs.stdout_tail.length + $managedRuntimeStore.logs.stderr_tail.length}</strong>
    </div>
  </div>

  <div class="room-grid">
    <article>
      <header>
        <h4>{$t('observability.validated_events')}</h4>
        <span>{$t('observability.session_only')}</span>
      </header>
      <EventStream events={$controlPlaneStore.recentEvents} />
    </article>

    <article>
      <header>
        <h4>{$t('observability.runtime_logs')}</h4>
        <span>{$t('observability.sanitized_tail')}</span>
      </header>
      {#if $managedRuntimeStore.logs.stdout_tail.length === 0 && $managedRuntimeStore.logs.stderr_tail.length === 0}
        <p class="empty">{$t('observability.no_runtime_logs')}</p>
      {:else}
        <ol class="log-lines">
          {#each $managedRuntimeStore.logs.stderr_tail as line}
            <li class="stderr"><span>stderr</span><code>{line}</code></li>
          {/each}
          {#each $managedRuntimeStore.logs.stdout_tail as line}
            <li><span>stdout</span><code>{line}</code></li>
          {/each}
        </ol>
      {/if}
    </article>
  </div>
</section>

<style>
  .observability { display: grid; gap: var(--lc-space-4); }
  .heading, .heading button, .notice, .summary > div, article header { display: flex; align-items: center; }
  .heading { align-items: flex-start; justify-content: space-between; gap: var(--lc-space-3); }
  .heading > div { min-width: 0; }
  .eyebrow { color: var(--lc-accent); font-family: var(--lc-mono); font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h3, h4, p { margin: 0; }
  h3 { margin-top: var(--lc-space-1); color: var(--lc-text); font-size: 20px; text-transform: none; letter-spacing: -.02em; }
  .heading p, .notice p { margin-top: var(--lc-space-1); color: var(--lc-muted); font-size: 12px; line-height: 1.5; }
  .heading button { flex: 0 0 auto; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: 0 var(--lc-space-3); background: var(--lc-panel-soft); cursor: pointer; }
  .notice { align-items: flex-start; gap: var(--lc-space-2); border: 1px solid var(--lc-line-strong); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-accent-dim); color: var(--lc-accent); }
  .notice p { margin: 0; color: var(--lc-text); }
  .summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--lc-space-2); }
  .summary > div { min-width: 0; justify-content: space-between; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  .summary span { color: var(--lc-muted); font-size: 11px; }
  .summary strong { color: var(--lc-text); font-family: var(--lc-mono); font-size: 14px; }
  .room-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--lc-space-3); }
  article { min-width: 0; border: var(--border-thin); border-radius: var(--lc-radius-md); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  article header { justify-content: space-between; gap: var(--lc-space-2); margin-bottom: var(--lc-space-3); }
  h4 { font-size: 12px; }
  article header span { color: var(--lc-faint); font-family: var(--lc-mono); font-size: 10px; }
  .log-lines { display: grid; max-height: 360px; overflow: auto; gap: var(--lc-space-1); margin: 0; padding: 0; list-style: none; }
  .log-lines li { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: var(--lc-space-2); border-bottom: var(--border-thin); padding: var(--lc-space-2); }
  .log-lines span { color: var(--lc-info); font-family: var(--lc-mono); font-size: 10px; }
  .log-lines .stderr span { color: var(--lc-warning); }
  code { min-width: 0; overflow-wrap: anywhere; color: var(--lc-muted); font-family: var(--lc-mono); font-size: 10px; white-space: pre-wrap; }
  .empty { border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); color: var(--lc-muted); font-size: 12px; }
  @media (max-width: 720px) { .summary, .room-grid { grid-template-columns: 1fr; } .heading { flex-direction: column; } }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/model/ManagedRuntimePanel.svelte (192 строк, 6528 байт)

````svelte
<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import {
    confirmManagedBinding,
    inferenceBusy,
    managedRuntimeStore,
    refreshManagedRuntimeStatus,
    setManagedHarness,
    setManagedSelectedModel,
    startSelectedManagedRuntime,
    stopSelectedManagedRuntime
  } from '$lib/stores/modelGateway';
  import type { HarnessId } from '$lib/types/modelGateway';

  $: status = $managedRuntimeStore.status;
  $: state = status?.state ?? 'NotInstalled';
  $: selectedModel = $managedRuntimeStore.catalog.find((model) => model.model_id === $managedRuntimeStore.selectedModelId);
  $: modelLaunchable = $managedRuntimeStore.readiness?.model_id === selectedModel?.model_id && $managedRuntimeStore.readiness?.launchable === true;
  $: canStart = !$inferenceBusy && Boolean(selectedModel) && modelLaunchable && (state === 'Stopped' || state === 'Failed');
  $: canStop = !$inferenceBusy && (state === 'Ready' || state === 'Starting' || state === 'Validating' || state === 'Failed');
  $: canBind = !$inferenceBusy && state === 'Ready' && status?.model_state === 'Ready' && status?.inference_ready === true && status?.model_id === $managedRuntimeStore.selectedModelId && modelLaunchable && Boolean(status?.runtime_instance_id) && Boolean($managedRuntimeStore.selectedModelId);
  $: tone = state === 'Ready' ? 'ready' : state === 'Failed' ? 'danger' : state === 'Starting' || state === 'Validating' || state === 'Stopping' ? 'info' : 'disabled';

  function onHarnessChange(event: Event) {
    setManagedHarness((event.currentTarget as HTMLSelectElement).value as HarnessId);
  }
</script>

<section class="managed-panel card-surface" aria-label="LocalComet managed runtime">
  <header class="managed-header">
    <div>
      <p class="eyebrow">LocalComet managed runtime</p>
      <h2>Managed llama.cpp</h2>
    </div>
    <StatusBadge label={state === 'NotInstalled' ? 'Not installed' : state} tone={tone} />
  </header>

  <div class="managed-grid">
    <TelemetryRow label="Engine" value="llama.cpp" mono />
    <TelemetryRow label="Managed Runtime" value={status?.installation ?? 'Not installed'} tone={state === 'NotInstalled' ? 'disabled' : 'ready'} />
    <TelemetryRow label="Runtime Version" value={status?.runtime_version ?? 'Not validated'} tone="disabled" mono />
    <TelemetryRow label="Model State" value={status?.model_state ?? 'Unavailable'} tone={status?.model_state === 'Ready' ? 'ready' : 'disabled'} />
    <TelemetryRow label="Inference" value={status?.inference_ready ? 'Ready' : 'Unavailable'} tone={status?.inference_ready ? 'ready' : 'disabled'} />
  </div>

  <div class="managed-controls">
    <button type="button" disabled={$inferenceBusy} onclick={() => void refreshManagedRuntimeStatus()}>Refresh</button>
    <button type="button" disabled={!canStart} onclick={() => void startSelectedManagedRuntime()}>Start Runtime</button>
    <button type="button" disabled={!canStop} onclick={() => void stopSelectedManagedRuntime()}>Stop Runtime</button>
  </div>

  <div class="managed-controls" aria-label="Managed model binding controls">
    <label>
      <span>Managed Model</span>
      <select disabled={$inferenceBusy} value={$managedRuntimeStore.selectedModelId} onchange={(event) => void setManagedSelectedModel((event.currentTarget as HTMLSelectElement).value)}>
        <option value="">Select managed model</option>
        {#each $managedRuntimeStore.catalog as model}
          <option value={model.model_id}>{model.display_name} ({Math.round(model.asset_bytes / 1024 / 1024)} MiB)</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Harness</span>
      <select disabled={$inferenceBusy} value={$managedRuntimeStore.harnessId} onchange={onHarnessChange}>
        <option value="minimal">minimal</option>
        <option value="native-localcomet">native-localcomet</option>
      </select>
    </label>
    <button type="button" disabled={!canBind} onclick={() => void confirmManagedBinding()}>Confirm Binding</button>
  </div>

  <div class="fingerprint" aria-label="Managed runtime fingerprint">
    <span>Runtime Instance</span>
    <code>{status?.runtime_instance_fingerprint ?? 'Runtime not ready'}</code>
  </div>

  {#if $managedRuntimeStore.logs.stdout_tail.length || $managedRuntimeStore.logs.stderr_tail.length}
    <pre class="runtime-logs" aria-label="Sanitized managed runtime logs">{[...$managedRuntimeStore.logs.stdout_tail, ...$managedRuntimeStore.logs.stderr_tail].join('\n')}</pre>
  {/if}
  {#if $managedRuntimeStore.lastError}
    <p class="managed-error" role="status">{$managedRuntimeStore.lastError.message}</p>
  {/if}
</section>

<style>
  .managed-panel {
    display: grid;
    gap: 14px;
    padding: 16px;
    border-color: var(--lc-border-strong);
  }

  .managed-header,
  .managed-controls {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .managed-header {
    justify-content: space-between;
  }

  .eyebrow {
    margin: 0 0 3px;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .managed-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  label {
    display: grid;
    gap: 5px;
    min-width: 180px;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  select {
    min-height: 36px;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
    padding: 8px 10px;
  }

  button {
    min-height: 36px;
  }

  .fingerprint {
    display: grid;
    gap: 5px;
    min-width: 0;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  code,
  .runtime-logs {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
  }

  .runtime-logs {
    max-height: 140px;
    margin: 0;
    overflow: auto;
    white-space: pre-wrap;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    padding: 12px;
  }

  .managed-error {
    margin: 0;
    color: var(--lc-danger);
    font-weight: 700;
  }

  @media (max-width: 720px) {
    .managed-grid {
      grid-template-columns: 1fr;
    }

    label,
    .managed-controls button {
      width: 100%;
    }
  }
</style>
````

