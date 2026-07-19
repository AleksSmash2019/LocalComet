use crate::control_plane::{BridgeError, ControlPlaneBridge, ControlPlaneMethod};
use crate::windows_job::{ContainedManagedRuntimeProcess, ManagedRuntimeLaunchSpec};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeSet;
use std::ffi::OsString;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Component, Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::State;

#[cfg(windows)]
use std::os::windows::fs::{MetadataExt, OpenOptionsExt};

#[cfg(windows)]
use windows_sys::Win32::Security::Cryptography::{
    BCryptGenRandom, BCRYPT_USE_SYSTEM_PREFERRED_RNG,
};

const ENGINE_ID: &str = "llama.cpp";
const EXECUTABLE_NAME: &str = "llama-server.exe";
const MANIFEST_NAME: &str = "runtime_manifest.json";
const MAX_MODELS: usize = 64;
const MIN_GGUF_BYTES: u64 = 1_048_576;
const MAX_GGUF_BYTES: u64 = 128 * 1024 * 1024 * 1024;
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
pub struct ManagedModelEntry {
    pub model_id: String,
    pub display_name: String,
    pub size_bytes: u64,
    pub availability: String,
    pub identity_fingerprint: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedModelCatalog {
    pub engine: &'static str,
    pub model_root: &'static str,
    pub models: Vec<ManagedModelEntry>,
    pub maximum_models: usize,
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

#[derive(Clone, Debug, Deserialize)]
struct RuntimeManifest {
    schema_version: String,
    runtime_id: String,
    engine: String,
    runtime_version: String,
    executable: String,
    manifest_sha256: String,
    files: Vec<RuntimeManifestFile>,
    required_cli_flags: Vec<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct RuntimeManifestFile {
    path: String,
    size_bytes: u64,
    sha256: String,
}

#[derive(Clone, Debug)]
struct ApprovedRuntime {
    runtime_id: &'static str,
    engine: &'static str,
    runtime_version: &'static str,
    manifest_sha256: &'static str,
    executable_sha256: &'static str,
    required_cli_flags: &'static [&'static str],
}

const APPROVED_RUNTIME_REGISTRY: &[ApprovedRuntime] = &[];

#[derive(Clone, Debug)]
struct RuntimeRoots {
    runtime_root: PathBuf,
    model_root: PathBuf,
    state_root: PathBuf,
}

#[derive(Clone, Debug)]
struct VerifiedRuntime {
    runtime_id: String,
    runtime_version: String,
    package_dir: PathBuf,
    executable: PathBuf,
}

#[derive(Clone, Debug)]
struct VerifiedModel {
    entry: ManagedModelEntry,
    path: PathBuf,
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
    model_entry: ManagedModelEntry,
    _model_handle: File,
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
    roots: RuntimeRoots,
    inner: Mutex<ManagedRuntimeInner>,
}

impl ManagedRuntimeSupervisor {
    pub fn production() -> Self {
        Self::new(production_roots())
    }

    fn new(roots: RuntimeRoots) -> Self {
        Self {
            roots,
            inner: Mutex::new(ManagedRuntimeInner::default()),
        }
    }

    pub fn status(&self) -> ManagedRuntimeStatus {
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        if inner.active.is_none() && !runtime_registry_has_installable() {
            inner.state = ManagedRuntimeState::NotInstalled;
        } else if inner.active.is_none() && inner.state == ManagedRuntimeState::NotInstalled {
            inner.state = ManagedRuntimeState::Stopped;
        }
        let active = inner.active.as_ref();
        ManagedRuntimeStatus {
            engine: ENGINE_ID,
            state: inner.state.clone(),
            installation: if runtime_registry_has_installable() {
                "Installed".into()
            } else {
                "Not installed".into()
            },
            runtime_version: inner.runtime_version.clone(),
            runtime_instance_id: active.map(|item| item.runtime_instance_id.clone()),
            runtime_instance_fingerprint: active
                .map(|item| item.runtime_instance_fingerprint.clone()),
            model_id: active.map(|item| item.model_entry.model_id.clone()),
            model_display_name: active.map(|item| item.model_entry.display_name.clone()),
            binding_fingerprint: active.map(|item| item.binding_fingerprint.clone()),
            last_error: inner.last_error.clone(),
        }
    }

    pub fn catalog(&self) -> Result<ManagedModelCatalog, ManagedRuntimeError> {
        fs::create_dir_all(&self.roots.model_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "model root unavailable"))?;
        ensure_local_safe_root(&self.roots.model_root)?;
        let mut models = Vec::new();
        let entries = fs::read_dir(&self.roots.model_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "model root scan failed"))?;
        for entry in entries.take(MAX_MODELS + 1) {
            let entry =
                entry.map_err(|_| ManagedRuntimeError::new("io_error", "model scan failed"))?;
            if models.len() >= MAX_MODELS {
                break;
            }
            if let Ok(model) = model_entry_from_path(&self.roots.model_root, &entry.path()) {
                models.push(model.entry);
            }
        }
        Ok(ManagedModelCatalog {
            engine: ENGINE_ID,
            model_root: "<MODEL_ROOT>",
            models,
            maximum_models: MAX_MODELS,
        })
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
        {
            let inner = self.inner.lock().expect("managed runtime lock poisoned");
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
        }

        self.set_state(ManagedRuntimeState::Validating, None);
        let start_result = self.start_inner(model_id);
        match start_result {
            Ok(response) => {
                let attach = self.attach_payload_for_active()?;
                if let Err(error) = bridge.request(ControlPlaneMethod::ModelManagedAttach, attach) {
                    let _ = self.stop(bridge);
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
                Err(error.into())
            }
        }
    }

    pub fn stop(
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
        inner.state = if runtime_registry_has_installable() {
            ManagedRuntimeState::Stopped
        } else {
            ManagedRuntimeState::NotInstalled
        };
        Ok(ManagedRuntimeStopResponse {
            state: inner.state.clone(),
            stopped: true,
        })
    }

    fn start_inner(
        &self,
        model_id: &str,
    ) -> Result<ManagedRuntimeStartResponse, ManagedRuntimeError> {
        if !runtime_registry_has_installable() {
            return Err(ManagedRuntimeError::new(
                "runtime_not_installed",
                "Managed Runtime: Not installed",
            ));
        }
        fs::create_dir_all(&self.roots.runtime_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "runtime root unavailable"))?;
        fs::create_dir_all(&self.roots.model_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "model root unavailable"))?;
        fs::create_dir_all(&self.roots.state_root)
            .map_err(|_| ManagedRuntimeError::new("io_error", "runtime state unavailable"))?;
        ensure_local_safe_root(&self.roots.runtime_root)?;
        ensure_local_safe_root(&self.roots.model_root)?;
        ensure_local_safe_root(&self.roots.state_root)?;

        let runtime = verify_first_approved_runtime(&self.roots.runtime_root)?;
        verify_runtime_capabilities(&runtime)?;
        let model = resolve_model_by_id(&self.roots.model_root, model_id)?;
        let model_handle = open_model_guard(&model.path)?;
        let identity_after = model_entry_from_path(&self.roots.model_root, &model.path)?;
        if identity_after.entry.identity_fingerprint != model.entry.identity_fingerprint {
            return Err(ManagedRuntimeError::new(
                "model_changed",
                "model identity changed before launch",
            ));
        }
        let credential = generate_credential()?;
        let api_key_file = write_private_api_key_file(&self.roots.state_root, &credential)?;
        let port = select_ephemeral_loopback_port()?;
        let alias = safe_alias(&model.entry.model_id);
        let runtime_instance_id = hex_bytes(&random_bytes(16)?);
        let runtime_instance_fingerprint = sha256_text(&format!(
            "{}:{}:{}",
            runtime.runtime_id, runtime.runtime_version, runtime_instance_id
        ));
        let binding_fingerprint = sha256_text(&format!(
            "managed:{}:{}:{}",
            runtime_instance_id, model.entry.model_id, model.entry.identity_fingerprint
        ));

        self.set_state(ManagedRuntimeState::Starting, None);
        let spec = ManagedRuntimeLaunchSpec {
            executable: runtime.executable.clone(),
            args: runtime_args(&model.path, port, &api_key_file, &alias),
            current_dir: runtime.package_dir.clone(),
            env: sanitized_runtime_environment(),
        };
        let mut process = ContainedManagedRuntimeProcess::spawn(&spec).map_err(|_| {
            ManagedRuntimeError::new("launch_failed", "managed runtime launch failed")
        })?;
        let inner = self.inner.lock().expect("managed runtime lock poisoned");
        let stdout_tail = Arc::clone(&inner.stdout_tail);
        let stderr_tail = Arc::clone(&inner.stderr_tail);
        drop(inner);
        let stdout_reader = process.take_stdout().map(|stdout| {
            spawn_log_reader(
                stdout,
                stdout_tail,
                self.redaction_markers(&credential, &api_key_file),
            )
        });
        let stderr_reader = process.take_stderr().map(|stderr| {
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
            let _ = fs::remove_file(&api_key_file);
            return Err(error);
        }

        let response = ManagedRuntimeStartResponse {
            state: ManagedRuntimeState::Ready,
            provider_id: "managed-llama-cpp",
            model_id: model.entry.model_id.clone(),
            model_display_name: model.entry.display_name.clone(),
            runtime_instance_id: runtime_instance_id.clone(),
            runtime_instance_fingerprint: runtime_instance_fingerprint.clone(),
        };
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        inner.runtime_version = Some(runtime.runtime_version);
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
            model_entry: model.entry,
            _model_handle: model_handle,
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
            "expected_model_alias": safe_alias(&active.model_entry.model_id),
            "model_id": active.model_entry.model_id,
            "binding_fingerprint": active.binding_fingerprint,
        }))
    }

    fn set_state(&self, state: ManagedRuntimeState, error: Option<&str>) {
        let mut inner = self.inner.lock().expect("managed runtime lock poisoned");
        inner.state = state;
        inner.last_error = error.map(|item| sanitize_text(item, 240));
    }

    fn redaction_markers(&self, credential: &str, api_key_file: &Path) -> Vec<(String, String)> {
        vec![
            (
                self.roots.runtime_root.to_string_lossy().into_owned(),
                "<RUNTIME_ROOT>".into(),
            ),
            (
                self.roots.model_root.to_string_lossy().into_owned(),
                "<MODEL_ROOT>".into(),
            ),
            (
                self.roots.state_root.to_string_lossy().into_owned(),
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
                let _ = fs::remove_file(&active.api_key_file);
                active.credential.clear();
            }
        }
    }
}

fn production_roots() -> RuntimeRoots {
    let local = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"C:\Users\Public\AppData\Local"));
    RuntimeRoots {
        runtime_root: local.join("LocalComet").join("runtimes").join(ENGINE_ID),
        model_root: local.join("LocalComet").join("models"),
        state_root: local.join("LocalComet").join("runtime-state"),
    }
}

fn runtime_registry_has_installable() -> bool {
    !APPROVED_RUNTIME_REGISTRY.is_empty()
}

fn verify_first_approved_runtime(
    runtime_root: &Path,
) -> Result<VerifiedRuntime, ManagedRuntimeError> {
    let approved = APPROVED_RUNTIME_REGISTRY.first().ok_or_else(|| {
        ManagedRuntimeError::new("runtime_not_installed", "Managed Runtime: Not installed")
    })?;
    let package_dir = runtime_root.join(approved.runtime_id);
    let manifest_path = package_dir.join(MANIFEST_NAME);
    let manifest = parse_runtime_manifest(&manifest_path)?;
    verify_manifest_against_approval(&manifest, approved, &manifest_path, &package_dir)?;
    Ok(VerifiedRuntime {
        runtime_id: manifest.runtime_id,
        runtime_version: manifest.runtime_version,
        executable: package_dir.join(EXECUTABLE_NAME),
        package_dir,
    })
}

fn parse_runtime_manifest(path: &Path) -> Result<RuntimeManifest, ManagedRuntimeError> {
    let body = fs::read(path).map_err(|_| {
        ManagedRuntimeError::new("runtime_not_installed", "runtime manifest missing")
    })?;
    if has_duplicate_json_key(&body) {
        return Err(ManagedRuntimeError::new(
            "invalid_manifest",
            "duplicate JSON key rejected",
        ));
    }
    serde_json::from_slice(&body)
        .map_err(|_| ManagedRuntimeError::new("invalid_manifest", "runtime manifest invalid"))
}

fn verify_manifest_against_approval(
    manifest: &RuntimeManifest,
    approved: &ApprovedRuntime,
    manifest_path: &Path,
    package_dir: &Path,
) -> Result<(), ManagedRuntimeError> {
    if manifest.schema_version != "1"
        || manifest.runtime_id != approved.runtime_id
        || manifest.engine != ENGINE_ID
        || manifest.engine != approved.engine
        || manifest.runtime_version != approved.runtime_version
        || manifest.executable != EXECUTABLE_NAME
    {
        return Err(ManagedRuntimeError::new(
            "invalid_manifest",
            "runtime manifest rejected",
        ));
    }
    let manifest_hash = sha256_file(manifest_path)?;
    if manifest.manifest_sha256 != manifest_hash || manifest_hash != approved.manifest_sha256 {
        return Err(ManagedRuntimeError::new(
            "runtime_not_approved",
            "runtime manifest hash is not approved",
        ));
    }
    for flag in approved.required_cli_flags {
        if !manifest.required_cli_flags.iter().any(|item| item == flag) {
            return Err(ManagedRuntimeError::new(
                "runtime_incompatible",
                "required runtime CLI flag missing",
            ));
        }
    }
    for flag in REQUIRED_FLAGS {
        if !manifest.required_cli_flags.iter().any(|item| item == flag) {
            return Err(ManagedRuntimeError::new(
                "runtime_incompatible",
                "required runtime CLI flag missing",
            ));
        }
    }
    let mut listed = BTreeSet::new();
    for file in &manifest.files {
        validate_manifest_relative_path(&file.path)?;
        if !listed.insert(file.path.clone()) {
            return Err(ManagedRuntimeError::new(
                "invalid_manifest",
                "duplicate file path",
            ));
        }
        let full = package_dir.join(&file.path);
        reject_reparse_point(&full)?;
        let meta = full
            .metadata()
            .map_err(|_| ManagedRuntimeError::new("invalid_manifest", "runtime file missing"))?;
        if !meta.is_file() || meta.len() != file.size_bytes {
            return Err(ManagedRuntimeError::new(
                "invalid_manifest",
                "runtime file size mismatch",
            ));
        }
        if sha256_file(&full)? != file.sha256 {
            return Err(ManagedRuntimeError::new(
                "invalid_manifest",
                "runtime file hash mismatch",
            ));
        }
    }
    let exe_hash = manifest
        .files
        .iter()
        .find(|item| item.path.eq_ignore_ascii_case(EXECUTABLE_NAME))
        .map(|item| item.sha256.as_str())
        .ok_or_else(|| {
            ManagedRuntimeError::new("invalid_manifest", "runtime executable missing")
        })?;
    if exe_hash != approved.executable_sha256 {
        return Err(ManagedRuntimeError::new(
            "runtime_not_approved",
            "runtime executable hash is not approved",
        ));
    }
    reject_unlisted_forbidden_files(package_dir, &listed)?;
    Ok(())
}

fn validate_manifest_relative_path(path: &str) -> Result<(), ManagedRuntimeError> {
    let candidate = Path::new(path);
    if candidate.is_absolute()
        || path.contains('\\')
        || path.contains('\0')
        || candidate
            .components()
            .any(|part| !matches!(part, Component::Normal(_)))
    {
        return Err(ManagedRuntimeError::new(
            "invalid_manifest",
            "runtime path rejected",
        ));
    }
    Ok(())
}

fn reject_unlisted_forbidden_files(
    package_dir: &Path,
    listed: &BTreeSet<String>,
) -> Result<(), ManagedRuntimeError> {
    for entry in fs::read_dir(package_dir)
        .map_err(|_| ManagedRuntimeError::new("invalid_manifest", "runtime package unreadable"))?
    {
        let entry = entry
            .map_err(|_| ManagedRuntimeError::new("invalid_manifest", "runtime scan failed"))?;
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().into_owned();
        if entry.file_type().map(|item| item.is_dir()).unwrap_or(false) {
            continue;
        }
        let lowered = name.to_ascii_lowercase();
        let forbidden = [".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".com"]
            .iter()
            .any(|suffix| lowered.ends_with(suffix));
        if forbidden && !listed.contains(&name) {
            return Err(ManagedRuntimeError::new(
                "invalid_manifest",
                "unlisted executable file rejected",
            ));
        }
        reject_reparse_point(&path)?;
    }
    Ok(())
}

fn verify_runtime_capabilities(runtime: &VerifiedRuntime) -> Result<(), ManagedRuntimeError> {
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
    runtime: &VerifiedRuntime,
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

fn model_entry_from_path(
    model_root: &Path,
    path: &Path,
) -> Result<VerifiedModel, ManagedRuntimeError> {
    reject_reparse_point(path)?;
    let canonical_root = model_root
        .canonicalize()
        .map_err(|_| ManagedRuntimeError::new("invalid_model", "model root invalid"))?;
    let canonical = path
        .canonicalize()
        .map_err(|_| ManagedRuntimeError::new("invalid_model", "model path invalid"))?;
    if canonical.parent() != Some(canonical_root.as_path()) {
        return Err(ManagedRuntimeError::new(
            "invalid_model",
            "model traversal rejected",
        ));
    }
    if canonical
        .extension()
        .and_then(|item| item.to_str())
        .map(|item| !item.eq_ignore_ascii_case("gguf"))
        .unwrap_or(true)
    {
        return Err(ManagedRuntimeError::new(
            "invalid_model",
            "non-GGUF model rejected",
        ));
    }
    let meta = canonical
        .metadata()
        .map_err(|_| ManagedRuntimeError::new("invalid_model", "model metadata unavailable"))?;
    if !meta.is_file() || meta.len() < MIN_GGUF_BYTES || meta.len() > MAX_GGUF_BYTES {
        return Err(ManagedRuntimeError::new(
            "invalid_model",
            "model size rejected",
        ));
    }
    let mut file = File::open(&canonical)
        .map_err(|_| ManagedRuntimeError::new("invalid_model", "model open failed"))?;
    let mut magic = [0_u8; 4];
    file.read_exact(&mut magic)
        .map_err(|_| ManagedRuntimeError::new("invalid_model", "model magic missing"))?;
    if &magic != b"GGUF" {
        return Err(ManagedRuntimeError::new(
            "invalid_model",
            "invalid GGUF magic",
        ));
    }
    let name = canonical
        .file_name()
        .and_then(|item| item.to_str())
        .ok_or_else(|| ManagedRuntimeError::new("invalid_model", "model name invalid"))?;
    let display_name = sanitize_model_name(name);
    let fingerprint = file_identity_fingerprint(&canonical, &meta);
    let model_id = format!("managed-{}", &fingerprint[..32]);
    Ok(VerifiedModel {
        path: canonical,
        entry: ManagedModelEntry {
            model_id,
            display_name,
            size_bytes: meta.len(),
            availability: "Available".into(),
            identity_fingerprint: fingerprint,
        },
    })
}

fn resolve_model_by_id(
    model_root: &Path,
    model_id: &str,
) -> Result<VerifiedModel, ManagedRuntimeError> {
    for entry in fs::read_dir(model_root)
        .map_err(|_| ManagedRuntimeError::new("invalid_model", "model root unavailable"))?
        .take(MAX_MODELS + 1)
    {
        let entry =
            entry.map_err(|_| ManagedRuntimeError::new("invalid_model", "model scan failed"))?;
        if let Ok(model) = model_entry_from_path(model_root, &entry.path()) {
            if model.entry.model_id == model_id {
                return Ok(model);
            }
        }
    }
    Err(ManagedRuntimeError::new(
        "invalid_model",
        "model_id not found",
    ))
}

#[cfg(windows)]
fn open_model_guard(path: &Path) -> Result<File, ManagedRuntimeError> {
    const GENERIC_READ: u32 = 0x8000_0000;
    const FILE_SHARE_READ: u32 = 0x0000_0001;
    OpenOptions::new()
        .read(true)
        .access_mode(GENERIC_READ)
        .share_mode(FILE_SHARE_READ)
        .open(path)
        .map_err(|_| ManagedRuntimeError::new("model_locked", "model file identity guard failed"))
}

#[cfg(not(windows))]
fn open_model_guard(path: &Path) -> Result<File, ManagedRuntimeError> {
    File::open(path)
        .map_err(|_| ManagedRuntimeError::new("model_locked", "model file identity guard failed"))
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

fn ensure_local_safe_root(path: &Path) -> Result<(), ManagedRuntimeError> {
    if path.to_string_lossy().starts_with(r"\\") {
        return Err(ManagedRuntimeError::new(
            "invalid_path",
            "UNC path rejected",
        ));
    }
    reject_reparse_point(path)?;
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

fn sha256_file(path: &Path) -> Result<String, ManagedRuntimeError> {
    let mut file = File::open(path)
        .map_err(|_| ManagedRuntimeError::new("io_error", "hash input unavailable"))?;
    let mut buffer = Vec::new();
    file.read_to_end(&mut buffer)
        .map_err(|_| ManagedRuntimeError::new("io_error", "hash read failed"))?;
    Ok(sha256_bytes(&buffer))
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

fn file_identity_fingerprint(path: &Path, meta: &fs::Metadata) -> String {
    #[cfg(windows)]
    {
        sha256_text(&format!(
            "{}:{}:{}:{}",
            path.file_name()
                .and_then(|item| item.to_str())
                .unwrap_or("model"),
            meta.file_size(),
            meta.creation_time(),
            meta.last_write_time()
        ))
    }
    #[cfg(not(windows))]
    {
        sha256_text(&format!(
            "{}:{}",
            path.file_name()
                .and_then(|item| item.to_str())
                .unwrap_or("model"),
            meta.len(),
        ))
    }
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

fn has_duplicate_json_key(body: &[u8]) -> bool {
    let Ok(text) = std::str::from_utf8(body) else {
        return false;
    };
    let mut stack: Vec<BTreeSet<String>> = Vec::new();
    let mut in_string = false;
    let mut escaped = false;
    let mut token = String::new();
    let mut expecting_key = false;
    let mut last_string: Option<String> = None;
    for ch in text.chars() {
        if in_string {
            if escaped {
                escaped = false;
                token.push(ch);
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
                last_string = Some(token.clone());
                token.clear();
            } else {
                token.push(ch);
            }
            continue;
        }
        match ch {
            '"' => in_string = true,
            '{' => {
                stack.push(BTreeSet::new());
                expecting_key = true;
                last_string = None;
            }
            '}' => {
                stack.pop();
                expecting_key = false;
                last_string = None;
            }
            ':' if expecting_key => {
                if let (Some(keys), Some(key)) = (stack.last_mut(), last_string.take()) {
                    if !keys.insert(key) {
                        return true;
                    }
                }
                expecting_key = false;
            }
            ',' => {
                expecting_key = !stack.is_empty();
                last_string = None;
            }
            _ => {}
        }
    }
    false
}

#[tauri::command]
pub fn managed_runtime_status(
    state: State<'_, Arc<ManagedRuntimeSupervisor>>,
) -> ManagedRuntimeStatus {
    state.status()
}

#[tauri::command]
pub fn managed_model_catalog(
    state: State<'_, Arc<ManagedRuntimeSupervisor>>,
) -> Result<ManagedModelCatalog, BridgeError> {
    state.catalog().map_err(BridgeError::from)
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
    fn production_registry_is_empty_and_llama_cpp_only() {
        assert!(APPROVED_RUNTIME_REGISTRY.is_empty());
        assert_eq!(ENGINE_ID, "llama.cpp");
        assert_eq!(EXECUTABLE_NAME, "llama-server.exe");
    }

    #[test]
    fn duplicate_json_keys_are_rejected() {
        assert!(has_duplicate_json_key(
            br#"{"schema_version":"1","schema_version":"2"}"#
        ));
        assert!(!has_duplicate_json_key(
            br#"{"schema_version":"1","files":[{"path":"a"}]}"#
        ));
    }

    #[test]
    fn manifest_paths_reject_absolute_and_traversal() {
        assert!(validate_manifest_relative_path("llama-server.exe").is_ok());
        assert!(validate_manifest_relative_path("../x").is_err());
        assert!(validate_manifest_relative_path("C:/x").is_err());
        assert!(validate_manifest_relative_path("dir/file.dll").is_ok());
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
