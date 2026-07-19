use crate::ipc;
use crate::windows_job::{ContainedSidecarProcess, SidecarLaunchSpec};
use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

#[cfg(debug_assertions)]
pub const PYTHON_ISOLATED_ARG: &str = "-I";
#[cfg(debug_assertions)]
pub const PYTHON_NO_BYTECODE_ARG: &str = "-B";
#[cfg(debug_assertions)]
pub const PYTHON_SIDECAR_RUNNER: &str = "tools/run_localcomet_desktop_sidecar.py";
#[cfg(not(debug_assertions))]
pub const RELEASE_SIDECAR_EXE: &str = "localcomet-core.exe";
pub const HEALTH_METHOD: &str = "app.health";
pub const SHUTDOWN_METHOD: &str = "app.shutdown";

pub trait SidecarFrameRouter: Send + Sync {
    fn route_frame(&self, frame: Vec<u8>);
    fn fail_pending(&self, code: &str, message: &str);
}

#[derive(Debug)]
pub enum SupervisorError {
    Unavailable(String),
    Io(io::Error),
}

impl std::fmt::Display for SupervisorError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unavailable(message) => write!(formatter, "sidecar unavailable: {message}"),
            Self::Io(error) => write!(formatter, "sidecar I/O error: {error}"),
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
            } => {
                if !executable.is_file() {
                    return Err(SupervisorError::Unavailable(
                        "release sidecar executable missing".into(),
                    ));
                }
                Ok(SidecarLaunchSpec {
                    executable: executable.clone(),
                    args: Vec::new(),
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
        Self {
            program: SidecarProgram::ReleaseBundle {
                executable,
                current_dir,
            },
            env: minimal_sidecar_environment(None),
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
    saw_goodbye: AtomicBool,
    last_frame: Mutex<Option<String>>,
    stderr_tail: Mutex<String>,
    router: Mutex<Option<Arc<dyn SidecarFrameRouter>>>,
}

#[derive(Clone, Debug)]
pub struct SupervisorSnapshot {
    pub running: bool,
    pub saw_python_hello: bool,
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
        let mut process = ContainedSidecarProcess::spawn(&spec)?;
        if let Some(stdout) = process.take_stdout() {
            spawn_stdout_reader(stdout, Arc::clone(&self.shared));
        }
        if let Some(stderr) = process.take_stderr() {
            spawn_stderr_reader(stderr, Arc::clone(&self.shared));
        }

        process.write_all(&ipc::desktop_hello_frame(
            "desk-hello-000001",
            "localcomet-desktop",
        )?)?;
        process.flush()?;
        state.process = Some(process);
        Ok(())
    }

    pub fn set_frame_router(&self, router: Arc<dyn SidecarFrameRouter>) {
        *self
            .shared
            .router
            .lock()
            .expect("sidecar router lock poisoned") = Some(router);
    }

    pub fn send_ipc_frame(&self, frame: Vec<u8>) -> Result<(), SupervisorError> {
        let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
        if state.shutting_down {
            return Err(SupervisorError::Unavailable("sidecar is stopping".into()));
        }
        let process = state
            .process
            .as_mut()
            .ok_or_else(|| SupervisorError::Unavailable("sidecar process is not running".into()))?;
        process.write_all(&frame)?;
        process.flush()?;
        Ok(())
    }

    pub fn send_health_probe(&self) -> Result<(), SupervisorError> {
        let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
        let sequence = state.next_request;
        state.next_request += 1;
        let process = state
            .process
            .as_mut()
            .ok_or_else(|| SupervisorError::Unavailable("sidecar process is not running".into()))?;
        process.write_all(&ipc::lifecycle_request_frame(
            &format!("desk-health-{sequence:06}"),
            HEALTH_METHOD,
            sequence,
        )?)?;
        process.flush()?;
        Ok(())
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
        let mut state = self.state.lock().expect("sidecar supervisor lock poisoned");
        if state.shutting_down {
            return Ok(());
        }
        state.shutting_down = true;
        let sequence = state.next_request;
        state.next_request += 1;
        if let Some(process) = state.process.as_mut() {
            process.write_all(&ipc::lifecycle_request_frame(
                &format!("desk-shutdown-{sequence:06}"),
                SHUTDOWN_METHOD,
                sequence,
            )?)?;
            process.flush()?;
            thread::sleep(Duration::from_millis(25));
        }
        state.process = None;
        self.fail_pending("sidecar_shutdown", "sidecar shutdown");
        Ok(())
    }

    fn fail_pending(&self, code: &str, message: &str) {
        if let Some(router) = self
            .shared
            .router
            .lock()
            .expect("sidecar router lock poisoned")
            .clone()
        {
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
                if text.contains("\"type\":\"hello\"") && text.contains("\"python_core\"") {
                    shared.saw_python_hello.store(true, Ordering::SeqCst);
                }
                if text.contains("\"type\":\"goodbye\"") {
                    shared.saw_goodbye.store(true, Ordering::SeqCst);
                }
                *shared
                    .last_frame
                    .lock()
                    .expect("sidecar frame lock poisoned") = Some(limit_text(&text, 4096));
                if let Some(router) = shared
                    .router
                    .lock()
                    .expect("sidecar router lock poisoned")
                    .clone()
                {
                    router.route_frame(frame);
                }
            }
            if let Some(router) = shared
                .router
                .lock()
                .expect("sidecar router lock poisoned")
                .clone()
            {
                router.fail_pending("sidecar_unavailable", "sidecar stdout closed");
            }
        });
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
    let path_value = std::env::var_os("PATH")?;
    for base in std::env::split_paths(&path_value) {
        for name in ["python.exe", "python3.exe", "py.exe"] {
            let candidate = base.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        let local_app_data_path = PathBuf::from(local_app_data);
        let python_launcher = local_app_data_path.join("Microsoft/WindowsApps/python.exe");
        if python_launcher.is_file() {
            return Some(python_launcher);
        }
        let python_launcher = local_app_data_path.join("Microsoft/WindowsApps/python3.exe");
        if python_launcher.is_file() {
            return Some(python_launcher);
        }
        let python_launcher = local_app_data_path.join("Microsoft/WindowsApps/py.exe");
        if python_launcher.is_file() {
            return Some(python_launcher);
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
            SidecarProgram::ReleaseBundle { executable, .. } => {
                assert!(executable.ends_with(RELEASE_SIDECAR_EXE));
            }
            _ => panic!("release sidecar executable expected"),
        }
    }

    #[test]
    fn real_python_sidecar_can_start_when_test_environment_is_present() {
        let Some(root) = std::env::var_os("LOCALCOMET_TEST_PROJECT_ROOT").map(PathBuf::from) else {
            return;
        };
        let Some(python) = std::env::var_os("LOCALCOMET_TEST_PYTHON").map(PathBuf::from) else {
            return;
        };
        let supervisor =
            DesktopSidecarSupervisor::new(SupervisorConfig::debug_for_tests(root, python));
        supervisor.start().unwrap();
        thread::sleep(Duration::from_millis(200));
        supervisor.send_health_probe().unwrap();
        thread::sleep(Duration::from_millis(200));
        let snapshot = supervisor.snapshot();
        assert!(snapshot.running);
        assert!(snapshot.saw_python_hello);
        supervisor.shutdown().unwrap();
    }
}
