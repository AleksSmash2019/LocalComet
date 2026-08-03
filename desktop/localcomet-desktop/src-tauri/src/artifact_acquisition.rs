use crate::artifact_trust::{
    source_controlled_runtime_license_bytes, ApprovedDownloadArtifact, ApprovedModelArtifact,
    ApprovedRuntimeArtifact, ArtifactKind, ArtifactTrustService, InstallationStatus,
    RuntimeArchiveMemberDisposition,
};
use crate::control_plane::{BridgeError, ControlPlaneBridge};
use crate::managed_runtime::{ManagedRuntimeState, ManagedRuntimeSupervisor};
use reqwest::blocking::{Client, Response};
use reqwest::redirect::Policy;
use reqwest::Url;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::State;
use zip::ZipArchive;

#[cfg(windows)]
use std::ffi::OsStr;
#[cfg(windows)]
use std::os::windows::ffi::OsStrExt;
#[cfg(windows)]
use windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW;

const MAX_REDIRECTS: usize = 5;
const DOWNLOAD_BUFFER_BYTES: usize = 64 * 1024;
const PROGRESS_UPDATE_BYTES: u64 = 512 * 1024;
const DISK_RESERVE_BYTES: u64 = 64 * 1024 * 1024;
const MAX_STALE_PARTIALS: usize = 64;
const MAX_RUNTIME_ARCHIVE_MEMBERS: usize = 128;
const ACQUISITION_EVENT_SCHEMA_VERSION: u32 = 1;

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactDownloadLifecycle {
    Idle,
    AwaitingConfirmation,
    CheckingDisk,
    Downloading,
    Cancelling,
    Cancelled,
    VerifyingSize,
    VerifyingHash,
    ValidatingArtifact,
    Installing,
    Completed,
    Failed,
}

impl ArtifactDownloadLifecycle {
    fn terminal(&self) -> bool {
        matches!(self, Self::Cancelled | Self::Completed | Self::Failed)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum AcquisitionFailureStage {
    Transfer,
    SizeVerification,
    HashVerification,
    ArchiveValidation,
    StagingExtraction,
    AtomicPromotion,
    PostInstallValidation,
}

#[derive(Serialize)]
struct AcquisitionFailureEvent<'a> {
    schema_version: u32,
    timestamp_utc_ms: u64,
    artifact_kind: &'static str,
    artifact_id: &'a str,
    terminal_status: &'static str,
    stage: AcquisitionFailureStage,
    error_code: &'a str,
    downloaded_bytes: u64,
    expected_bytes: u64,
    archive_member: Option<&'a str>,
    archive_disposition: Option<RuntimeArchiveMemberDisposition>,
    expected_member_count: Option<u64>,
    observed_member_count: Option<u64>,
    cleanup_complete: bool,
    final_artifact_exists: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ArtifactDownloadState {
    pub job_id: String,
    pub artifact_id: String,
    pub lifecycle: ArtifactDownloadLifecycle,
    pub expected_bytes: u64,
    pub received_bytes: u64,
    pub percent: Option<u8>,
    pub started_utc_ms: u64,
    pub updated_utc_ms: u64,
    pub error_code: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ApprovedDownloadableArtifact {
    pub artifact_id: String,
    pub kind: ArtifactKind,
    pub display_name: String,
    pub source_identity: String,
    pub expected_bytes: u64,
    pub license_id: String,
    pub format: Option<String>,
    pub quantization: Option<String>,
    pub user_confirmation_required: bool,
    pub automatic_download: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedModelRemovalResult {
    pub model_id: String,
    pub removed: bool,
}

#[derive(Clone)]
pub struct ArtifactAcquisitionManager {
    artifacts: Arc<ArtifactTrustService>,
    jobs: Arc<Mutex<DownloadRegistry>>,
    job_sequence: Arc<AtomicU64>,
    diagnostic_lock: Arc<Mutex<()>>,
}

#[derive(Default)]
struct DownloadRegistry {
    jobs: HashMap<String, DownloadJob>,
    active_by_artifact: HashMap<String, String>,
}

struct DownloadJob {
    state: ArtifactDownloadState,
    cancel_requested: Arc<AtomicBool>,
}

#[derive(Debug)]
struct AcquisitionError {
    code: &'static str,
    archive_member: Option<String>,
    archive_disposition: Option<RuntimeArchiveMemberDisposition>,
    expected_member_count: Option<u64>,
    observed_member_count: Option<u64>,
}

impl AcquisitionError {
    fn new(code: &'static str) -> Self {
        Self {
            code,
            archive_member: None,
            archive_disposition: None,
            expected_member_count: None,
            observed_member_count: None,
        }
    }

    fn archive_member(
        mut self,
        member: String,
        disposition: Option<RuntimeArchiveMemberDisposition>,
    ) -> Self {
        self.archive_member = Some(member);
        self.archive_disposition = disposition;
        self
    }

    fn archive_member_counts(mut self, expected: usize, observed: usize) -> Self {
        self.expected_member_count = Some(expected as u64);
        self.observed_member_count = Some(observed as u64);
        self
    }
}

impl ArtifactAcquisitionManager {
    pub fn new(artifacts: Arc<ArtifactTrustService>) -> Self {
        let manager = Self {
            artifacts,
            jobs: Arc::new(Mutex::new(DownloadRegistry::default())),
            job_sequence: Arc::new(AtomicU64::new(0)),
            diagnostic_lock: Arc::new(Mutex::new(())),
        };
        manager.cleanup_stale_partials();
        manager
    }

    pub fn approved_artifacts(&self) -> Vec<ApprovedDownloadableArtifact> {
        let mut approved = Vec::new();
        for runtime in self.artifacts.runtime_catalog().runtimes {
            approved.push(ApprovedDownloadableArtifact {
                artifact_id: runtime.runtime_id,
                kind: ArtifactKind::Runtime,
                display_name: format!("llama.cpp {}", runtime.release_tag),
                source_identity: runtime.upstream_repository,
                expected_bytes: runtime.asset_bytes,
                license_id: runtime.license_id,
                format: Some(runtime.archive_format),
                quantization: None,
                user_confirmation_required: true,
                automatic_download: false,
            });
        }
        for model in self.artifacts.model_catalog().models {
            approved.push(ApprovedDownloadableArtifact {
                artifact_id: model.model_id,
                kind: ArtifactKind::Model,
                display_name: model.display_name,
                source_identity: model.upstream_repository,
                expected_bytes: model.asset_bytes,
                license_id: model.license_id,
                format: Some(model.format),
                quantization: Some(model.quantization),
                user_confirmation_required: true,
                automatic_download: false,
            });
        }
        approved
    }

    pub fn start(
        &self,
        artifact_id: &str,
        confirmed: bool,
    ) -> Result<ArtifactDownloadState, BridgeError> {
        if !confirmed {
            return Err(BridgeError::new(
                "confirmation_required",
                "approved artifact download requires confirmation",
            ));
        }
        let artifact = self
            .artifacts
            .approved_download_artifact(artifact_id)
            .map_err(BridgeError::from)?;
        let current = self
            .artifacts
            .artifact_validation_status(artifact_id)
            .map_err(BridgeError::from)?;
        if current.installation_status == InstallationStatus::Valid {
            let mut completed = self.new_state(
                artifact_id,
                current.expected_bytes,
                ArtifactDownloadLifecycle::Completed,
            );
            completed.received_bytes = current.expected_bytes;
            completed.percent = percent(current.expected_bytes, current.expected_bytes);
            let mut registry = self.jobs.lock().expect("download registry poisoned");
            registry.jobs.insert(
                completed.job_id.clone(),
                DownloadJob {
                    state: completed.clone(),
                    cancel_requested: Arc::new(AtomicBool::new(false)),
                },
            );
            return Ok(completed);
        }
        if current.installation_status != InstallationStatus::NotInstalled {
            return Err(BridgeError::new(
                "conflicting_installed_artifact",
                "approved artifact is present but not valid",
            ));
        }
        let destination = self
            .artifacts
            .download_destination(&artifact)
            .map_err(BridgeError::from)?;
        if destination.exists() {
            return Err(BridgeError::new(
                "conflicting_installed_artifact",
                "approved artifact destination already exists",
            ));
        }
        let expected_bytes = expected_bytes(&artifact);
        let mut state =
            self.new_state(artifact_id, expected_bytes, ArtifactDownloadLifecycle::Idle);
        state.lifecycle = ArtifactDownloadLifecycle::AwaitingConfirmation;
        state.updated_utc_ms = now_utc_ms();
        let cancel_requested = Arc::new(AtomicBool::new(false));
        {
            let mut registry = self.jobs.lock().expect("download registry poisoned");
            if let Some(existing_id) = registry.active_by_artifact.get(artifact_id) {
                return registry
                    .jobs
                    .get(existing_id)
                    .map(|job| job.state.clone())
                    .ok_or_else(|| {
                        BridgeError::new("download_conflict", "active download unavailable")
                    });
            }
            registry
                .active_by_artifact
                .insert(artifact_id.to_string(), state.job_id.clone());
            registry.jobs.insert(
                state.job_id.clone(),
                DownloadJob {
                    state: state.clone(),
                    cancel_requested: Arc::clone(&cancel_requested),
                },
            );
        }
        let manager = self.clone();
        let job_id = state.job_id.clone();
        thread::spawn(move || manager.run_job(job_id, artifact, cancel_requested));
        Ok(state)
    }

    pub fn get(&self, job_id: &str) -> Result<ArtifactDownloadState, BridgeError> {
        validate_job_id(job_id)?;
        self.jobs
            .lock()
            .expect("download registry poisoned")
            .jobs
            .get(job_id)
            .map(|job| job.state.clone())
            .ok_or_else(|| BridgeError::new("unknown_download_job", "download job is unavailable"))
    }

    pub fn cancel(&self, job_id: &str) -> Result<ArtifactDownloadState, BridgeError> {
        validate_job_id(job_id)?;
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let job = registry.jobs.get_mut(job_id).ok_or_else(|| {
            BridgeError::new("unknown_download_job", "download job is unavailable")
        })?;
        if !job.state.lifecycle.terminal() {
            job.cancel_requested.store(true, Ordering::Release);
            job.state.lifecycle = ArtifactDownloadLifecycle::Cancelling;
            job.state.updated_utc_ms = now_utc_ms();
        }
        Ok(job.state.clone())
    }

    pub fn remove_model(
        &self,
        model_id: &str,
        confirmed: bool,
        runtime: &ManagedRuntimeSupervisor,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedModelRemovalResult, BridgeError> {
        if !confirmed {
            return Err(BridgeError::new(
                "confirmation_required",
                "managed model removal requires confirmation",
            ));
        }
        let artifact = self
            .artifacts
            .approved_download_artifact(model_id)
            .map_err(BridgeError::from)?;
        let ApprovedDownloadArtifact::Model(_) = artifact else {
            return Err(BridgeError::new(
                "invalid_artifact_kind",
                "managed artifact is not a model",
            ));
        };
        let status = runtime.status(bridge);
        if status.model_id.as_deref() == Some(model_id)
            || matches!(
                status.state,
                ManagedRuntimeState::Validating
                    | ManagedRuntimeState::Starting
                    | ManagedRuntimeState::Ready
                    | ManagedRuntimeState::Stopping
            )
        {
            return Err(BridgeError::new(
                "model_active",
                "disconnect the managed model before removal",
            ));
        }
        let validation = self
            .artifacts
            .artifact_validation_status(model_id)
            .map_err(BridgeError::from)?;
        if validation.installation_status != InstallationStatus::Valid {
            return Err(BridgeError::new(
                "model_not_installed",
                "managed model is not valid",
            ));
        }
        let destination = self
            .artifacts
            .download_destination(&artifact)
            .map_err(BridgeError::from)?;
        fs::remove_file(&destination).map_err(|_| {
            BridgeError::new("model_removal_failed", "managed model removal failed")
        })?;
        self.artifacts
            .invalidate_validation_cache_for_artifact(model_id);
        self.prune_empty_model_parents(&destination);
        Ok(ManagedModelRemovalResult {
            model_id: model_id.to_string(),
            removed: true,
        })
    }

    fn run_job(
        &self,
        job_id: String,
        artifact: ApprovedDownloadArtifact,
        cancel_requested: Arc<AtomicBool>,
    ) {
        let result = self.download_and_install(&job_id, &artifact, &cancel_requested);
        match result {
            Ok(()) => {
                self.cleanup_job_temporary_resources(&job_id);
                self.complete(&job_id, ArtifactDownloadLifecycle::Completed, None);
            }
            Err(error) if error.code == "cancelled" => {
                self.cleanup_job_temporary_resources(&job_id);
                self.complete(&job_id, ArtifactDownloadLifecycle::Cancelled, None);
            }
            Err(error) => {
                self.persist_terminal_failure_before_cleanup(&job_id, &artifact, &error);
                self.complete(&job_id, ArtifactDownloadLifecycle::Failed, Some(error.code));
            }
        }
    }

    fn download_and_install(
        &self,
        job_id: &str,
        artifact: &ApprovedDownloadArtifact,
        cancel_requested: &AtomicBool,
    ) -> Result<(), AcquisitionError> {
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::CheckingDisk, None);
        self.require_not_cancelled(cancel_requested)?;
        let destination = self
            .artifacts
            .download_destination(artifact)
            .map_err(|_| AcquisitionError::new("invalid_destination"))?;
        if destination.exists() {
            return Err(AcquisitionError::new("conflicting_installed_artifact"));
        }
        let acquisition_root = self
            .artifacts
            .acquisition_root()
            .map_err(|_| AcquisitionError::new("acquisition_storage_unavailable"))?;
        let partial = acquisition_root.join(format!("{job_id}.partial"));
        if partial.exists() {
            return Err(AcquisitionError::new("partial_name_conflict"));
        }
        let required_space = required_disk_space(artifact)?;
        if available_space(&acquisition_root)? < required_space {
            return Err(AcquisitionError::new("insufficient_disk_space"));
        }
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::Downloading, None);
        self.download_to_partial(job_id, artifact, &partial, cancel_requested)?;
        self.artifacts
            .invalidate_validation_cache_for_artifact(artifact_id(artifact));
        self.require_not_cancelled(cancel_requested)?;
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::VerifyingSize, None);
        let expected = expected_bytes(artifact);
        let actual = fs::metadata(&partial)
            .map_err(|_| AcquisitionError::new("partial_unavailable"))?
            .len();
        if actual != expected {
            return Err(AcquisitionError::new("size_mismatch"));
        }
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::VerifyingHash, None);
        if sha256_file(&partial, Some(cancel_requested))? != expected_sha256(artifact) {
            return Err(AcquisitionError::new("hash_mismatch"));
        }
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::ValidatingArtifact, None);
        self.require_not_cancelled(cancel_requested)?;
        match artifact {
            ApprovedDownloadArtifact::Model(model) => {
                validate_model_partial(&partial, model)?;
                self.set_lifecycle(job_id, ArtifactDownloadLifecycle::Installing, None);
                self.require_not_cancelled(cancel_requested)?;
                install_model(&partial, &destination)?;
            }
            ApprovedDownloadArtifact::Runtime(runtime) => {
                self.set_lifecycle(job_id, ArtifactDownloadLifecycle::Installing, None);
                let staging = acquisition_root.join(format!("{job_id}.runtime-staging"));
                extract_and_install_runtime(
                    &partial,
                    &staging,
                    &destination,
                    runtime,
                    cancel_requested,
                )?;
            }
        }
        self.artifacts
            .invalidate_validation_cache_for_artifact(artifact_id(artifact));
        if let Err(error) = self.require_not_cancelled(cancel_requested) {
            remove_installed_artifact(artifact, &destination);
            self.artifacts
                .invalidate_validation_cache_for_artifact(artifact_id(artifact));
            return Err(error);
        }
        let validation = self
            .artifacts
            .artifact_validation_status(artifact_id(artifact))
            .map_err(|_| AcquisitionError::new("post_install_validation_failed"))?;
        if validation.installation_status != InstallationStatus::Valid {
            remove_installed_artifact(artifact, &destination);
            self.artifacts
                .invalidate_validation_cache_for_artifact(artifact_id(artifact));
            return Err(AcquisitionError::new("post_install_validation_failed"));
        }
        remove_owned_file(&partial);
        Ok(())
    }

    fn download_to_partial(
        &self,
        job_id: &str,
        artifact: &ApprovedDownloadArtifact,
        partial: &Path,
        cancel_requested: &AtomicBool,
    ) -> Result<(), AcquisitionError> {
        let mut response = open_approved_response(artifact)?;
        validate_content_type(&response, artifact)?;
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(partial)
            .map_err(|_| AcquisitionError::new("partial_create_failed"))?;
        let expected = expected_bytes(artifact);
        let mut received = 0_u64;
        let mut last_reported = 0_u64;
        let mut buffer = [0_u8; DOWNLOAD_BUFFER_BYTES];
        loop {
            self.require_not_cancelled(cancel_requested)?;
            let read = response
                .read(&mut buffer)
                .map_err(|_| AcquisitionError::new("download_failed"))?;
            if read == 0 {
                break;
            }
            received = received
                .checked_add(read as u64)
                .ok_or_else(|| AcquisitionError::new("size_mismatch"))?;
            if received > expected {
                return Err(AcquisitionError::new("size_mismatch"));
            }
            file.write_all(&buffer[..read])
                .map_err(|_| AcquisitionError::new("partial_write_failed"))?;
            if received.saturating_sub(last_reported) >= PROGRESS_UPDATE_BYTES
                || received == expected
            {
                self.set_progress(job_id, received);
                last_reported = received;
            }
        }
        file.flush()
            .and_then(|_| file.sync_all())
            .map_err(|_| AcquisitionError::new("partial_write_failed"))?;
        self.set_progress(job_id, received);
        Ok(())
    }

    fn set_lifecycle(
        &self,
        job_id: &str,
        lifecycle: ArtifactDownloadLifecycle,
        error_code: Option<&'static str>,
    ) {
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let Some(job) = registry.jobs.get_mut(job_id) else {
            return;
        };
        if job.state.lifecycle.terminal() {
            return;
        }
        job.state.lifecycle = lifecycle;
        job.state.error_code = error_code.map(str::to_owned);
        job.state.updated_utc_ms = now_utc_ms();
    }

    fn set_progress(&self, job_id: &str, received_bytes: u64) {
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let Some(job) = registry.jobs.get_mut(job_id) else {
            return;
        };
        if job.state.lifecycle.terminal() {
            return;
        }
        job.state.received_bytes = received_bytes.min(job.state.expected_bytes);
        job.state.percent = percent(job.state.received_bytes, job.state.expected_bytes);
        job.state.updated_utc_ms = now_utc_ms();
    }

    fn complete(
        &self,
        job_id: &str,
        lifecycle: ArtifactDownloadLifecycle,
        error_code: Option<&'static str>,
    ) {
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let artifact_id = {
            let Some(job) = registry.jobs.get_mut(job_id) else {
                return;
            };
            if job.state.lifecycle.terminal() {
                return;
            }
            job.state.lifecycle = lifecycle;
            job.state.error_code = error_code.map(str::to_owned);
            job.state.updated_utc_ms = now_utc_ms();
            job.state.artifact_id.clone()
        };
        registry.active_by_artifact.remove(&artifact_id);
    }

    fn new_state(
        &self,
        artifact_id: &str,
        expected_bytes: u64,
        lifecycle: ArtifactDownloadLifecycle,
    ) -> ArtifactDownloadState {
        let timestamp = now_utc_ms();
        ArtifactDownloadState {
            job_id: self.next_job_id(),
            artifact_id: artifact_id.to_string(),
            lifecycle,
            expected_bytes,
            received_bytes: 0,
            percent: percent(0, expected_bytes),
            started_utc_ms: timestamp,
            updated_utc_ms: timestamp,
            error_code: None,
        }
    }

    fn next_job_id(&self) -> String {
        let counter = self.job_sequence.fetch_add(1, Ordering::Relaxed);
        let mut hasher = Sha256::new();
        hasher.update(now_utc_ms().to_le_bytes());
        hasher.update(counter.to_le_bytes());
        hasher.update(std::process::id().to_le_bytes());
        format!("{:x}", hasher.finalize())
    }

    fn require_not_cancelled(&self, cancel_requested: &AtomicBool) -> Result<(), AcquisitionError> {
        if cancel_requested.load(Ordering::Acquire) {
            return Err(AcquisitionError::new("cancelled"));
        }
        Ok(())
    }

    fn cleanup_stale_partials(&self) {
        let Ok(root) = self.artifacts.acquisition_root() else {
            return;
        };
        let Ok(entries) = fs::read_dir(root) else {
            return;
        };
        for entry in entries.flatten().take(MAX_STALE_PARTIALS) {
            let path = entry.path();
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if is_owned_partial_name(&name)
                && entry
                    .file_type()
                    .map(|kind| kind.is_file())
                    .unwrap_or(false)
            {
                let _ = fs::remove_file(path);
            } else if is_owned_runtime_staging_name(&name)
                && entry.file_type().map(|kind| kind.is_dir()).unwrap_or(false)
            {
                let _ = fs::remove_dir_all(path);
            }
        }
    }

    fn remove_job_partial(&self, job_id: &str) {
        let Ok(root) = self.artifacts.acquisition_root() else {
            return;
        };
        remove_owned_file(&root.join(format!("{job_id}.partial")));
    }

    fn cleanup_job_temporary_resources(&self, job_id: &str) -> bool {
        let Ok(root) = self.artifacts.acquisition_root() else {
            return false;
        };
        let partial = root.join(format!("{job_id}.partial"));
        let staging = root.join(format!("{job_id}.runtime-staging"));
        self.remove_job_partial(job_id);
        if staging.exists() {
            let _ = fs::remove_dir_all(&staging);
        }
        !partial.exists() && !staging.exists()
    }

    fn persist_terminal_failure_before_cleanup(
        &self,
        job_id: &str,
        artifact: &ApprovedDownloadArtifact,
        error: &AcquisitionError,
    ) {
        let downloaded_bytes = self.current_received_bytes(job_id);
        let expected_bytes = expected_bytes(artifact);
        let stage = acquisition_failure_stage(error.code);
        let final_artifact_exists = self.final_artifact_exists(artifact);
        let before_cleanup = AcquisitionFailureEvent {
            schema_version: ACQUISITION_EVENT_SCHEMA_VERSION,
            timestamp_utc_ms: now_utc_ms(),
            artifact_kind: acquisition_artifact_kind(artifact),
            artifact_id: artifact_id(artifact),
            terminal_status: "failed",
            stage,
            error_code: error.code,
            downloaded_bytes,
            expected_bytes,
            archive_member: error.archive_member.as_deref(),
            archive_disposition: error.archive_disposition,
            expected_member_count: error.expected_member_count,
            observed_member_count: error.observed_member_count,
            cleanup_complete: false,
            final_artifact_exists,
        };
        let _ = self.append_failure_event(&before_cleanup);
        let cleanup_complete = self.cleanup_job_temporary_resources(job_id);
        let after_cleanup = AcquisitionFailureEvent {
            timestamp_utc_ms: now_utc_ms(),
            cleanup_complete,
            final_artifact_exists: self.final_artifact_exists(artifact),
            ..before_cleanup
        };
        let _ = self.append_failure_event(&after_cleanup);
    }

    fn current_received_bytes(&self, job_id: &str) -> u64 {
        self.jobs
            .lock()
            .expect("download registry poisoned")
            .jobs
            .get(job_id)
            .map(|job| job.state.received_bytes)
            .unwrap_or(0)
    }

    fn final_artifact_exists(&self, artifact: &ApprovedDownloadArtifact) -> bool {
        self.artifacts
            .download_destination(artifact)
            .map(|path| path.exists())
            .unwrap_or(false)
    }

    fn append_failure_event(&self, event: &AcquisitionFailureEvent<'_>) -> Result<(), ()> {
        let path = self
            .artifacts
            .acquisition_event_log_path()
            .map_err(|_| ())?;
        let mut bytes = serde_json::to_vec(event).map_err(|_| ())?;
        bytes.push(b'\n');
        let _guard = self.diagnostic_lock.lock().map_err(|_| ())?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|_| ())?;
        file.write_all(&bytes)
            .and_then(|_| file.sync_data())
            .map_err(|_| ())
    }

    fn prune_empty_model_parents(&self, destination: &Path) {
        let root = &self.artifacts.roots().model_root;
        let mut current = destination.parent();
        while let Some(directory) = current {
            if directory == root || !directory.starts_with(root) {
                break;
            }
            if fs::remove_dir(directory).is_err() {
                break;
            }
            current = directory.parent();
        }
    }
}

fn acquisition_artifact_kind(artifact: &ApprovedDownloadArtifact) -> &'static str {
    match artifact {
        ApprovedDownloadArtifact::Runtime(_) => "runtime",
        ApprovedDownloadArtifact::Model(_) => "model",
    }
}

fn acquisition_failure_stage(error_code: &str) -> AcquisitionFailureStage {
    match error_code {
        "size_mismatch" => AcquisitionFailureStage::SizeVerification,
        "hash_mismatch" | "hash_read_failed" => AcquisitionFailureStage::HashVerification,
        "invalid_runtime_archive"
        | "unexpected_runtime_member"
        | "runtime_member_hash_mismatch"
        | "missing_runtime_member"
        | "archive_member_count_mismatch" => AcquisitionFailureStage::ArchiveValidation,
        "staging_create_failed" | "staging_write_failed" | "license_asset_invalid" => {
            AcquisitionFailureStage::StagingExtraction
        }
        "atomic_install_failed" => AcquisitionFailureStage::AtomicPromotion,
        "post_install_validation_failed" => AcquisitionFailureStage::PostInstallValidation,
        _ => AcquisitionFailureStage::Transfer,
    }
}

#[tauri::command]
pub fn list_approved_downloadable_artifacts(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
) -> Vec<ApprovedDownloadableArtifact> {
    state.approved_artifacts()
}

#[tauri::command]
pub fn start_approved_artifact_download(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
    approval: State<'_, crate::approval_commands::ApprovalState>,
    artifact_id: String,
    confirmed: bool,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<ArtifactDownloadState, BridgeError> {
    let _ = confirmed;
    let input = serde_json::json!({ "artifact_id": artifact_id });
    crate::approval_commands::validate_approval_token(
        &approval,
        "artifact.download",
        &input,
        &token,
        &approval_id,
        &call_id,
    )?;
    state.start(&artifact_id, true)
}

#[tauri::command]
pub fn get_artifact_download_state(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
    job_id: String,
) -> Result<ArtifactDownloadState, BridgeError> {
    state.get(&job_id)
}

#[tauri::command]
pub fn cancel_artifact_download(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
    job_id: String,
) -> Result<ArtifactDownloadState, BridgeError> {
    state.cancel(&job_id)
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub fn remove_managed_model(
    acquisition: State<'_, Arc<ArtifactAcquisitionManager>>,
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
    approval: State<'_, crate::approval_commands::ApprovalState>,
    model_id: String,
    confirmed: bool,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<ManagedModelRemovalResult, BridgeError> {
    let _ = confirmed;
    let input = serde_json::json!({ "model_id": model_id });
    crate::approval_commands::validate_approval_token(
        &approval,
        "artifact.remove",
        &input,
        &token,
        &approval_id,
        &call_id,
    )?;
    acquisition.remove_model(&model_id, true, &runtime, &bridge)
}

fn artifact_id(artifact: &ApprovedDownloadArtifact) -> &str {
    match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => &runtime.runtime_id,
        ApprovedDownloadArtifact::Model(model) => &model.model_id,
    }
}

fn expected_bytes(artifact: &ApprovedDownloadArtifact) -> u64 {
    match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => runtime.acquisition.expected_bytes,
        ApprovedDownloadArtifact::Model(model) => model.acquisition.expected_bytes,
    }
}

fn expected_sha256(artifact: &ApprovedDownloadArtifact) -> &str {
    match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => &runtime.acquisition.expected_sha256,
        ApprovedDownloadArtifact::Model(model) => &model.acquisition.expected_sha256,
    }
}

fn required_disk_space(artifact: &ApprovedDownloadArtifact) -> Result<u64, AcquisitionError> {
    let downloaded = expected_bytes(artifact);
    let install_reserve = match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => runtime
            .required_files
            .iter()
            .try_fold(0_u64, |total, file| total.checked_add(file.bytes))
            .and_then(|total| total.checked_add(runtime.license_asset.bytes))
            .ok_or_else(|| AcquisitionError::new("disk_requirement_overflow"))?,
        ApprovedDownloadArtifact::Model(_) => DISK_RESERVE_BYTES,
    };
    downloaded
        .checked_add(install_reserve)
        .and_then(|value| value.checked_add(DISK_RESERVE_BYTES))
        .ok_or_else(|| AcquisitionError::new("disk_requirement_overflow"))
}

fn open_approved_response(
    artifact: &ApprovedDownloadArtifact,
) -> Result<Response, AcquisitionError> {
    let acquisition = match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => &runtime.acquisition,
        ApprovedDownloadArtifact::Model(model) => &model.acquisition,
    };
    let client = Client::builder()
        .redirect(Policy::none())
        .no_proxy()
        .connect_timeout(Duration::from_secs(15))
        .build()
        .map_err(|_| AcquisitionError::new("download_client_unavailable"))?;
    let mut current = Url::parse(&acquisition.primary_url)
        .map_err(|_| AcquisitionError::new("invalid_catalog_url"))?;
    for _ in 0..=MAX_REDIRECTS {
        validate_redirect_url(&current, &acquisition.allowed_redirect_hosts)?;
        let response = client
            .get(current.clone())
            .send()
            .map_err(|_| AcquisitionError::new("download_failed"))?;
        if response.status().is_redirection() {
            let location = response
                .headers()
                .get(reqwest::header::LOCATION)
                .and_then(|header| header.to_str().ok())
                .ok_or_else(|| AcquisitionError::new("redirect_rejected"))?;
            let next = current
                .join(location)
                .map_err(|_| AcquisitionError::new("redirect_rejected"))?;
            validate_redirect_url(&next, &acquisition.allowed_redirect_hosts)?;
            current = next;
            continue;
        }
        if !response.status().is_success() {
            return Err(AcquisitionError::new("download_failed"));
        }
        return Ok(response);
    }
    Err(AcquisitionError::new("redirect_limit_exceeded"))
}

fn validate_redirect_url(url: &Url, allowed_hosts: &[String]) -> Result<(), AcquisitionError> {
    let Some(host) = url.host_str() else {
        return Err(AcquisitionError::new("redirect_rejected"));
    };
    if url.scheme() != "https"
        || url.port().is_some()
        || !url.username().is_empty()
        || url.password().is_some()
        || !allowed_hosts.iter().any(|allowed| allowed == host)
    {
        return Err(AcquisitionError::new("redirect_rejected"));
    }
    Ok(())
}

fn validate_content_type(
    response: &Response,
    artifact: &ApprovedDownloadArtifact,
) -> Result<(), AcquisitionError> {
    let expected = match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => runtime.acquisition.content_type.as_deref(),
        ApprovedDownloadArtifact::Model(model) => model.acquisition.content_type.as_deref(),
    };
    let Some(expected) = expected else {
        return Ok(());
    };
    let Some(actual) = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|header| header.to_str().ok())
    else {
        return Ok(());
    };
    let actual = actual.split(';').next().unwrap_or_default().trim();
    if actual.eq_ignore_ascii_case(expected) {
        Ok(())
    } else {
        Err(AcquisitionError::new("content_type_mismatch"))
    }
}

fn validate_model_partial(
    path: &Path,
    model: &ApprovedModelArtifact,
) -> Result<(), AcquisitionError> {
    if !model
        .acquisition
        .expected_filename
        .to_ascii_lowercase()
        .ends_with(".gguf")
    {
        return Err(AcquisitionError::new("invalid_model_format"));
    }
    let mut magic = [0_u8; 4];
    File::open(path)
        .and_then(|mut file| file.read_exact(&mut magic))
        .map_err(|_| AcquisitionError::new("invalid_model_format"))?;
    if &magic != b"GGUF" {
        return Err(AcquisitionError::new("invalid_model_format"));
    }
    Ok(())
}

fn install_model(partial: &Path, destination: &Path) -> Result<(), AcquisitionError> {
    fs::rename(partial, destination).map_err(|_| AcquisitionError::new("atomic_install_failed"))
}

fn extract_and_install_runtime(
    partial: &Path,
    staging: &Path,
    destination: &Path,
    runtime: &ApprovedRuntimeArtifact,
    cancel_requested: &AtomicBool,
) -> Result<(), AcquisitionError> {
    if staging.exists() || destination.exists() {
        return Err(AcquisitionError::new("conflicting_installed_artifact"));
    }
    fs::create_dir(staging).map_err(|_| AcquisitionError::new("staging_create_failed"))?;
    (|| {
        let file =
            File::open(partial).map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
        let mut archive =
            ZipArchive::new(file).map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
        let envelope = runtime
            .archive_members
            .iter()
            .map(|member| {
                (
                    member.relative_path.to_ascii_lowercase(),
                    member.disposition,
                )
            })
            .collect::<BTreeMap<_, _>>();
        let archive_member_count = archive.len();
        if archive_member_count == 0 || archive_member_count > MAX_RUNTIME_ARCHIVE_MEMBERS {
            return Err(AcquisitionError::new("archive_member_count_mismatch")
                .archive_member_counts(envelope.len(), archive_member_count));
        }
        let required = runtime
            .required_files
            .iter()
            .map(|file| (file.relative_path.to_ascii_lowercase(), file))
            .collect::<BTreeMap<_, _>>();
        let mut seen = BTreeSet::new();
        let mut archive_indexes = BTreeMap::new();
        for index in 0..archive_member_count {
            let member = archive
                .by_index(index)
                .map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
            let name = member.name().to_string();
            let folded = safe_zip_member_name(&name)?;
            let disposition = envelope.get(&folded).copied();
            let regular_file = !member.is_dir()
                && member
                    .unix_mode()
                    .is_none_or(|mode| matches!(mode & 0o170000, 0 | 0o100000));
            if !regular_file {
                return Err(AcquisitionError::new("invalid_runtime_archive")
                    .archive_member(folded, disposition)
                    .archive_member_counts(envelope.len(), archive_member_count));
            }
            let Some(disposition) = disposition else {
                return Err(AcquisitionError::new("unexpected_runtime_member")
                    .archive_member(folded, None)
                    .archive_member_counts(envelope.len(), archive_member_count));
            };
            if !seen.insert(folded.clone()) {
                return Err(AcquisitionError::new("invalid_runtime_archive")
                    .archive_member(folded, Some(disposition))
                    .archive_member_counts(envelope.len(), archive_member_count));
            }
            archive_indexes.insert(folded, index);
        }
        if seen.len() != envelope.len() {
            let missing = envelope
                .iter()
                .find(|(name, _)| !seen.contains(*name))
                .map(|(name, disposition)| (name.clone(), *disposition))
                .expect("envelope count mismatch has a missing member");
            return Err(AcquisitionError::new("missing_runtime_member")
                .archive_member(missing.0, Some(missing.1))
                .archive_member_counts(envelope.len(), seen.len()));
        }
        for (folded, expected) in &required {
            if cancel_requested.load(Ordering::Acquire) {
                return Err(AcquisitionError::new("cancelled"));
            }
            if envelope.get(folded) != Some(&RuntimeArchiveMemberDisposition::Install) {
                return Err(AcquisitionError::new("invalid_runtime_archive")
                    .archive_member(folded.clone(), envelope.get(folded).copied()));
            }
            let index = archive_indexes.get(folded).copied().ok_or_else(|| {
                AcquisitionError::new("missing_runtime_member").archive_member(
                    folded.clone(),
                    Some(RuntimeArchiveMemberDisposition::Install),
                )
            })?;
            let mut member = archive
                .by_index(index)
                .map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
            let output = contained_staging_path(staging, &expected.relative_path)?;
            let mut output_file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(output)
                .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
            std::io::copy(&mut member, &mut output_file)
                .and_then(|_| output_file.sync_all())
                .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
            let path = contained_staging_path(staging, &expected.relative_path)?;
            let metadata =
                fs::metadata(&path).map_err(|_| AcquisitionError::new("staging_write_failed"))?;
            if metadata.len() != expected.bytes
                || sha256_file(&path, Some(cancel_requested))? != expected.sha256
            {
                return Err(AcquisitionError::new("runtime_member_hash_mismatch"));
            }
        }
        let license_bytes = source_controlled_runtime_license_bytes(&runtime.license_asset)
            .map_err(|_| AcquisitionError::new("license_asset_invalid"))?;
        let license_path =
            contained_staging_path(staging, &runtime.license_asset.destination_relative_path)?;
        let mut license_file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&license_path)
            .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
        license_file
            .write_all(license_bytes)
            .and_then(|_| license_file.sync_all())
            .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
        drop(license_file);
        let license_metadata = fs::metadata(&license_path)
            .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
        if license_metadata.len() != runtime.license_asset.bytes
            || sha256_file(&license_path, Some(cancel_requested))? != runtime.license_asset.sha256
        {
            return Err(AcquisitionError::new("license_asset_invalid"));
        }
        fs::rename(staging, destination)
            .map_err(|_| AcquisitionError::new("atomic_install_failed"))?;
        Ok(())
    })()
}

fn safe_zip_member_name(value: &str) -> Result<String, AcquisitionError> {
    if value.is_empty()
        || value.len() > 240
        || value.starts_with('/')
        || value.starts_with('\\')
        || value.contains('\\')
        || value.contains(':')
        || value.contains('\0')
        || value.ends_with('/')
    {
        return Err(AcquisitionError::new("invalid_runtime_archive"));
    }
    for segment in value.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." || segment.ends_with([' ', '.'])
        {
            return Err(AcquisitionError::new("invalid_runtime_archive"));
        }
    }
    Ok(value.to_ascii_lowercase())
}

fn contained_staging_path(root: &Path, member: &str) -> Result<PathBuf, AcquisitionError> {
    safe_zip_member_name(member)?;
    let mut path = root.to_path_buf();
    for segment in member.split('/') {
        path.push(segment);
    }
    if !path.starts_with(root) {
        return Err(AcquisitionError::new("invalid_runtime_archive"));
    }
    Ok(path)
}

fn sha256_file(
    path: &Path,
    cancel_requested: Option<&AtomicBool>,
) -> Result<String, AcquisitionError> {
    let mut file = File::open(path).map_err(|_| AcquisitionError::new("hash_read_failed"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; DOWNLOAD_BUFFER_BYTES];
    loop {
        if cancel_requested.is_some_and(|cancel| cancel.load(Ordering::Acquire)) {
            return Err(AcquisitionError::new("cancelled"));
        }
        let read = file
            .read(&mut buffer)
            .map_err(|_| AcquisitionError::new("hash_read_failed"))?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn remove_installed_artifact(artifact: &ApprovedDownloadArtifact, destination: &Path) {
    match artifact {
        ApprovedDownloadArtifact::Runtime(_) if destination.exists() => {
            let _ = fs::remove_dir_all(destination);
        }
        ApprovedDownloadArtifact::Model(_) if destination.exists() => {
            let _ = fs::remove_file(destination);
        }
        _ => {}
    }
}

fn remove_owned_file(path: &Path) {
    if path
        .file_name()
        .and_then(|value| value.to_str())
        .is_some_and(is_owned_partial_name)
    {
        let _ = fs::remove_file(path);
    }
}

fn is_owned_partial_name(value: &str) -> bool {
    value.strip_suffix(".partial").is_some_and(is_opaque_job_id)
}

fn is_owned_runtime_staging_name(value: &str) -> bool {
    value
        .strip_suffix(".runtime-staging")
        .is_some_and(is_opaque_job_id)
}

fn is_opaque_job_id(job_id: &str) -> bool {
    job_id.len() == 64
        && job_id
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn validate_job_id(value: &str) -> Result<(), BridgeError> {
    if value.len() != 64
        || value
            .bytes()
            .any(|byte| !(byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)))
    {
        return Err(BridgeError::new(
            "invalid_download_job",
            "download job id rejected",
        ));
    }
    Ok(())
}

fn percent(received: u64, expected: u64) -> Option<u8> {
    if expected == 0 {
        return None;
    }
    Some(((received.saturating_mul(100) / expected).min(100)) as u8)
}

fn now_utc_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().min(u64::MAX as u128) as u64)
        .unwrap_or(0)
}

#[cfg(windows)]
fn available_space(path: &Path) -> Result<u64, AcquisitionError> {
    let mut available = 0_u64;
    let mut total = 0_u64;
    let mut free = 0_u64;
    let mut wide: Vec<u16> = OsStr::new(path)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let result =
        unsafe { GetDiskFreeSpaceExW(wide.as_mut_ptr(), &mut available, &mut total, &mut free) };
    if result == 0 {
        return Err(AcquisitionError::new("disk_space_unavailable"));
    }
    Ok(available)
}

#[cfg(not(windows))]
fn available_space(_path: &Path) -> Result<u64, AcquisitionError> {
    Ok(u64::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::artifact_trust::{
        AcquisitionArtifactKind, AcquisitionSourceType, ApprovedArtifactAcquisition,
        ApprovedArtifactCatalog, ApprovedRuntimeArchiveMember, ApprovedRuntimeFile,
        ApprovedRuntimeLicenseAsset, CatalogStatus, ManagedArtifactRoots,
    };
    use std::sync::atomic::AtomicU64;
    use zip::write::SimpleFileOptions;

    const TEST_RUNTIME_ID: &str = "test-runtime";
    const TEST_MODEL_ID: &str = "test-model";
    const TEST_RUNTIME_BYTES: &[u8] = b"test-runtime";
    const TEST_MODEL_BYTES: &[u8] = b"GGUFtest-model";

    static TEST_SEQUENCE: AtomicU64 = AtomicU64::new(0);

    struct TestWorkspace {
        root: PathBuf,
    }

    impl TestWorkspace {
        fn new() -> Self {
            let sequence = TEST_SEQUENCE.fetch_add(1, Ordering::Relaxed);
            let root = std::env::temp_dir().join(format!(
                "localcomet-artifact-acquisition-{}-{}-{sequence}",
                std::process::id(),
                now_utc_ms()
            ));
            fs::create_dir_all(&root).expect("create test workspace");
            Self { root }
        }

        fn roots(&self) -> ManagedArtifactRoots {
            ManagedArtifactRoots {
                app_data_root: self.root.clone(),
                runtime_root: self.root.join("runtimes"),
                model_root: self.root.join("models"),
                state_root: self.root.join("state"),
            }
        }
    }

    impl Drop for TestWorkspace {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    fn sha256_bytes(bytes: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(bytes);
        format!("{:x}", hasher.finalize())
    }

    fn test_runtime() -> ApprovedRuntimeArtifact {
        ApprovedRuntimeArtifact {
            runtime_id: TEST_RUNTIME_ID.into(),
            provider: "test-provider".into(),
            release_tag: "b1".into(),
            platform: "windows".into(),
            architecture: "x86-64".into(),
            variant: "cpu".into(),
            upstream_repository: "test/runtime".into(),
            upstream_revision: "1111111111111111111111111111111111111111".into(),
            asset_filename: "test-runtime.zip".into(),
            asset_bytes: 7,
            asset_sha256: sha256_bytes(b"archive"),
            acquisition: ApprovedArtifactAcquisition {
                artifact_id: TEST_RUNTIME_ID.into(),
                artifact_kind: AcquisitionArtifactKind::Runtime,
                source_type: AcquisitionSourceType::ApprovedHttps,
                primary_url: "https://assets.example.test/test-runtime.zip".into(),
                allowed_redirect_hosts: vec!["assets.example.test".into()],
                expected_filename: "test-runtime.zip".into(),
                expected_bytes: 7,
                expected_sha256: sha256_bytes(b"archive"),
                content_type: Some("application/octet-stream".into()),
                managed_relative_destination: TEST_RUNTIME_ID.into(),
                public_distribution: false,
                installer_bundled: false,
                automatic_download: false,
                user_confirmation_required: true,
            },
            archive_format: "zip".into(),
            managed_relative_path: TEST_RUNTIME_ID.into(),
            executable_relative_path: "llama-server.exe".into(),
            archive_members: vec![ApprovedRuntimeArchiveMember {
                relative_path: "llama-server.exe".into(),
                disposition: RuntimeArchiveMemberDisposition::Install,
            }],
            required_files: vec![ApprovedRuntimeFile {
                relative_path: "llama-server.exe".into(),
                bytes: TEST_RUNTIME_BYTES.len() as u64,
                sha256: sha256_bytes(TEST_RUNTIME_BYTES),
            }],
            license_asset: ApprovedRuntimeLicenseAsset {
                source_relative_path: "third_party/llama.cpp/LICENSE-MIT.txt".into(),
                destination_relative_path: "LICENSE-MIT.txt".into(),
                bytes: 1_078,
                sha256: "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d".into(),
            },
            permitted_bind_scope: "loopback-only".into(),
            supported_api_protocol: "openai-compatible-v1".into(),
            license_id: "MIT".into(),
            public_distribution: false,
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_model() -> ApprovedModelArtifact {
        ApprovedModelArtifact {
            model_id: TEST_MODEL_ID.into(),
            provider: "test-provider".into(),
            family: "test-family".into(),
            display_name: "Test model".into(),
            format: "GGUF".into(),
            quantization: "Q4_K_M".into(),
            upstream_repository: "test/model".into(),
            upstream_revision: "2222222222222222222222222222222222222222".into(),
            asset_filename: "test-model.gguf".into(),
            asset_bytes: TEST_MODEL_BYTES.len() as u64,
            asset_sha256: sha256_bytes(TEST_MODEL_BYTES),
            acquisition: ApprovedArtifactAcquisition {
                artifact_id: TEST_MODEL_ID.into(),
                artifact_kind: AcquisitionArtifactKind::Model,
                source_type: AcquisitionSourceType::ApprovedHttps,
                primary_url: "https://assets.example.test/test-model.gguf".into(),
                allowed_redirect_hosts: vec!["assets.example.test".into()],
                expected_filename: "test-model.gguf".into(),
                expected_bytes: TEST_MODEL_BYTES.len() as u64,
                expected_sha256: sha256_bytes(TEST_MODEL_BYTES),
                content_type: Some("application/octet-stream".into()),
                managed_relative_destination: "test-model/test-model.gguf".into(),
                public_distribution: false,
                installer_bundled: false,
                automatic_download: false,
                user_confirmation_required: true,
            },
            license_id: "Apache-2.0".into(),
            compatible_runtime_ids: vec![TEST_RUNTIME_ID.into()],
            managed_relative_path: "test-model/test-model.gguf".into(),
            public_distribution: false,
            installer_bundled: false,
            bootstrap_purpose: "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION".into(),
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_manager() -> (
        TestWorkspace,
        ArtifactAcquisitionManager,
        Arc<ArtifactTrustService>,
    ) {
        let workspace = TestWorkspace::new();
        let catalog = ApprovedArtifactCatalog {
            schema_version: 1,
            catalog_id: "localcomet-approved-artifacts".into(),
            catalog_version: "1.0.0-test".into(),
            runtimes: vec![test_runtime()],
            models: vec![test_model()],
        };
        let mut bytes = serde_json::to_vec_pretty(&catalog).expect("serialize test catalog");
        bytes.push(b'\n');
        let trust = Arc::new(
            ArtifactTrustService::from_catalog_bytes(&bytes, workspace.roots())
                .expect("create test trust service"),
        );
        let manager = ArtifactAcquisitionManager::new(Arc::clone(&trust));
        (workspace, manager, trust)
    }

    fn write_zip(path: &Path, entries: &[(&str, &[u8])]) {
        let file = File::create(path).expect("create archive");
        let mut writer = zip::ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        for (name, bytes) in entries {
            writer
                .start_file(*name, options)
                .expect("start archive entry");
            writer.write_all(bytes).expect("write archive entry");
        }
        writer.finish().expect("finish archive");
    }

    fn write_owned_zip(path: &Path, entries: &[(String, Vec<u8>)]) {
        let file = File::create(path).expect("create archive");
        let mut writer = zip::ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        for (name, bytes) in entries {
            writer
                .start_file(name, options)
                .expect("start archive entry");
            writer.write_all(bytes).expect("write archive entry");
        }
        writer.finish().expect("finish archive");
    }

    fn embedded_runtime() -> ApprovedRuntimeArtifact {
        let catalog: ApprovedArtifactCatalog = serde_json::from_slice(include_bytes!(
            "../resources/localcomet/approved-artifacts.v1.json"
        ))
        .expect("parse embedded approved catalog");
        catalog
            .runtimes
            .into_iter()
            .next()
            .expect("approved runtime fixture")
    }

    fn approved_runtime_envelope_fixture() -> (ApprovedRuntimeArtifact, Vec<(String, Vec<u8>)>) {
        let mut runtime = embedded_runtime();
        let entries = runtime
            .archive_members
            .iter()
            .map(|member| {
                let prefix = match member.disposition {
                    RuntimeArchiveMemberDisposition::Install => "install",
                    RuntimeArchiveMemberDisposition::RecognizedNotInstalled => "recognized",
                };
                (
                    member.relative_path.clone(),
                    format!("{prefix}:{}", member.relative_path).into_bytes(),
                )
            })
            .collect::<Vec<_>>();
        runtime.required_files = runtime
            .archive_members
            .iter()
            .filter(|member| member.disposition == RuntimeArchiveMemberDisposition::Install)
            .map(|member| {
                let bytes = format!("install:{}", member.relative_path).into_bytes();
                ApprovedRuntimeFile {
                    relative_path: member.relative_path.clone(),
                    bytes: bytes.len() as u64,
                    sha256: sha256_bytes(&bytes),
                }
            })
            .collect();
        (runtime, entries)
    }

    fn top_level_names(path: &Path) -> BTreeSet<String> {
        fs::read_dir(path)
            .expect("read final runtime directory")
            .map(|entry| {
                entry
                    .expect("runtime directory entry")
                    .file_name()
                    .to_string_lossy()
                    .to_ascii_lowercase()
            })
            .collect()
    }

    fn register_job(
        manager: &ArtifactAcquisitionManager,
        artifact_id: &str,
        expected_bytes: u64,
        received_bytes: u64,
    ) -> String {
        let mut state = manager.new_state(
            artifact_id,
            expected_bytes,
            ArtifactDownloadLifecycle::Installing,
        );
        state.received_bytes = received_bytes;
        state.percent = percent(received_bytes, expected_bytes);
        let job_id = state.job_id.clone();
        let mut registry = manager.jobs.lock().expect("download registry");
        registry
            .active_by_artifact
            .insert(artifact_id.into(), job_id.clone());
        registry.jobs.insert(
            job_id.clone(),
            DownloadJob {
                state,
                cancel_requested: Arc::new(AtomicBool::new(false)),
            },
        );
        job_id
    }

    fn read_failure_events(trust: &ArtifactTrustService) -> Vec<serde_json::Value> {
        let path = trust.acquisition_event_log_path().expect("diagnostic path");
        let contents = fs::read_to_string(path).expect("read diagnostic events");
        contents
            .lines()
            .map(|line| serde_json::from_str(line).expect("diagnostic event JSON"))
            .collect()
    }

    #[test]
    fn model_redirect_authority_requires_exact_https_host() {
        let allowed = vec![
            "cas-bridge.xethub.hf.co".to_string(),
            "cdn-lfs-us-1.hf.co".to_string(),
            "cdn-lfs.hf.co".to_string(),
            "huggingface.co".to_string(),
            "transfer.xethub.hf.co".to_string(),
            "us.aws.cdn.hf.co".to_string(),
        ];
        assert!(validate_redirect_url(
            &Url::parse(
                "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf",
            )
            .expect("valid primary URL"),
            &allowed,
        )
        .is_ok());
        for host in &allowed {
            assert!(validate_redirect_url(
                &Url::parse(&format!("https://{host}/download")).expect("valid approved URL"),
                &allowed,
            )
            .is_ok());
        }
        for value in [
            "http://us.aws.cdn.hf.co/download",
            "https://us.aws.cdn.hf.co.attacker.example/download",
            "https://attacker-us.aws.cdn.hf.co/download",
            "https://aws.cdn.hf.co/download",
            "https://cdn.hf.co/download",
            "https://us.aws.cdn.hf.co./download",
            "https://us.aws.cdn.hf.co:8443/download",
            "https://user@us.aws.cdn.hf.co/download",
            "https://user:password@us.aws.cdn.hf.co/download",
            "https://127.0.0.1/download",
        ] {
            assert!(
                validate_redirect_url(&Url::parse(value).expect("valid URL"), &allowed).is_err()
            );
        }
    }

    #[test]
    fn runtime_archive_members_reject_windows_and_traversal_forms() {
        assert_eq!(
            safe_zip_member_name("llama-server.exe").expect("safe member"),
            "llama-server.exe"
        );
        for member in [
            "../llama-server.exe",
            "C:/llama-server.exe",
            "a\\b.dll",
            "/root.dll",
        ] {
            assert!(safe_zip_member_name(member).is_err());
        }
    }

    #[test]
    fn stale_cleanup_names_are_limited_to_opaque_job_resources() {
        let job_id = "a".repeat(64);
        assert!(is_owned_partial_name(&format!("{job_id}.partial")));
        assert!(is_owned_runtime_staging_name(&format!(
            "{job_id}.runtime-staging"
        )));
        assert!(!is_owned_partial_name("model.gguf.partial"));
        assert!(!is_owned_runtime_staging_name("runtime-staging"));
    }

    #[test]
    fn model_validation_rejects_bad_gguf_magic_before_installation() {
        let workspace = TestWorkspace::new();
        let partial = workspace.root.join("invalid.partial");
        fs::write(&partial, b"not-a-gguf").expect("write invalid model");

        let error = validate_model_partial(&partial, &test_model()).expect_err("reject bad magic");

        assert_eq!(error.code, "invalid_model_format");
    }

    #[test]
    fn runtime_archive_rejects_traversal_duplicate_and_bad_member_hash() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for (name, entries, expected_code) in [
            (
                "traversal.zip",
                vec![("../llama-server.exe", TEST_RUNTIME_BYTES)],
                "invalid_runtime_archive",
            ),
            (
                "duplicate.zip",
                vec![
                    ("llama-server.exe", TEST_RUNTIME_BYTES),
                    ("LLAMA-SERVER.EXE", TEST_RUNTIME_BYTES),
                ],
                "invalid_runtime_archive",
            ),
            (
                "bad-hash.zip",
                vec![("llama-server.exe", b"wrong".as_slice())],
                "runtime_member_hash_mismatch",
            ),
        ] {
            let archive = workspace.root.join(name);
            let staging = workspace.root.join(format!("{name}.staging"));
            let destination = workspace.root.join(format!("{name}.destination"));
            write_zip(&archive, &entries);

            let error = extract_and_install_runtime(
                &archive,
                &staging,
                &destination,
                &test_runtime(),
                &cancel,
            )
            .expect_err("reject unsafe archive");

            assert_eq!(error.code, expected_code);
            assert!(staging.exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
            assert!(!staging.exists());
            assert!(!destination.exists());
        }
    }

    #[test]
    fn runtime_archive_rejects_directory_members_before_staging_them() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        let archive = workspace.root.join("directory-member.zip");
        let staging = workspace.root.join("directory-member.staging");
        let destination = workspace.root.join("directory-member.destination");
        let file = File::create(&archive).expect("create archive");
        let mut writer = zip::ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        writer
            .add_directory("llama-server.exe/", options)
            .expect("add directory entry");
        writer.finish().expect("finish archive");

        let error =
            extract_and_install_runtime(&archive, &staging, &destination, &test_runtime(), &cancel)
                .expect_err("directory archive member must be rejected");

        assert_eq!(error.code, "invalid_runtime_archive");
        assert!(!destination.exists());
        assert!(top_level_names(&staging).is_empty());
    }

    #[test]
    fn approved_runtime_envelope_installs_only_the_pinned_subset_and_license() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        let (runtime, entries) = approved_runtime_envelope_fixture();
        assert_eq!(runtime.archive_members.len(), 51);
        assert_eq!(runtime.required_files.len(), 30);
        assert_eq!(
            runtime
                .archive_members
                .iter()
                .filter(|member| {
                    member.disposition == RuntimeArchiveMemberDisposition::RecognizedNotInstalled
                })
                .count(),
            21
        );

        let archive = workspace.root.join("approved-runtime.zip");
        let staging = workspace.root.join("approved-runtime.staging");
        let destination = workspace.root.join("approved-runtime.destination");
        write_owned_zip(&archive, &entries);
        extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
            .expect("approved envelope installs");

        assert!(!staging.exists());
        let mut expected = runtime
            .required_files
            .iter()
            .map(|file| file.relative_path.to_ascii_lowercase())
            .collect::<BTreeSet<_>>();
        expected.insert(
            runtime
                .license_asset
                .destination_relative_path
                .to_ascii_lowercase(),
        );
        assert_eq!(top_level_names(&destination), expected);
        for skipped in runtime.archive_members.iter().filter(|member| {
            member.disposition == RuntimeArchiveMemberDisposition::RecognizedNotInstalled
        }) {
            assert!(
                !destination.join(&skipped.relative_path).exists(),
                "recognized but uninstalled member escaped extraction: {}",
                skipped.relative_path
            );
        }
    }

    #[test]
    fn runtime_envelope_rejects_unknown_executable_library_and_text_members() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for unknown in ["unknown.exe", "unknown.dll", "manifest.txt"] {
            let (runtime, mut entries) = approved_runtime_envelope_fixture();
            entries.push((unknown.into(), b"unexpected".to_vec()));
            let archive = workspace.root.join(format!("{unknown}.zip"));
            let staging = workspace.root.join(format!("{unknown}.staging"));
            let destination = workspace.root.join(format!("{unknown}.destination"));
            write_owned_zip(&archive, &entries);

            let error =
                extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                    .expect_err("unknown envelope member must be rejected");

            assert_eq!(error.code, "unexpected_runtime_member");
            assert_eq!(error.archive_member.as_deref(), Some(unknown));
            assert_eq!(error.expected_member_count, Some(51));
            assert_eq!(error.observed_member_count, Some(52));
            assert!(!destination.exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
        }
    }

    #[test]
    fn runtime_envelope_rejects_missing_members_and_disposition_drift_before_promotion() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for (missing_name, expected_disposition) in [
            ("llama-server.exe", RuntimeArchiveMemberDisposition::Install),
            (
                "llama-bench.exe",
                RuntimeArchiveMemberDisposition::RecognizedNotInstalled,
            ),
        ] {
            let (runtime, mut entries) = approved_runtime_envelope_fixture();
            entries.retain(|(name, _)| name != missing_name);
            let archive = workspace.root.join(format!("missing-{missing_name}.zip"));
            let staging = workspace
                .root
                .join(format!("missing-{missing_name}.staging"));
            let destination = workspace
                .root
                .join(format!("missing-{missing_name}.destination"));
            write_owned_zip(&archive, &entries);

            let error =
                extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                    .expect_err("missing envelope member must be rejected");

            assert_eq!(error.code, "missing_runtime_member");
            assert_eq!(error.archive_member.as_deref(), Some(missing_name));
            assert_eq!(error.archive_disposition, Some(expected_disposition));
            assert_eq!(error.expected_member_count, Some(51));
            assert_eq!(error.observed_member_count, Some(50));
            assert!(!destination.exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
        }

        let (mut runtime, entries) = approved_runtime_envelope_fixture();
        runtime
            .archive_members
            .iter_mut()
            .find(|member| member.relative_path == "llama-server.exe")
            .expect("launcher envelope member")
            .disposition = RuntimeArchiveMemberDisposition::RecognizedNotInstalled;
        let archive = workspace.root.join("disposition-drift.zip");
        let staging = workspace.root.join("disposition-drift.staging");
        let destination = workspace.root.join("disposition-drift.destination");
        write_owned_zip(&archive, &entries);

        let error =
            extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                .expect_err("installable launcher cannot become recognized-only");

        assert_eq!(error.code, "invalid_runtime_archive");
        assert_eq!(error.archive_member.as_deref(), Some("llama-server.exe"));
        assert_eq!(
            error.archive_disposition,
            Some(RuntimeArchiveMemberDisposition::RecognizedNotInstalled)
        );
        assert!(!destination.exists());
        fs::remove_dir_all(&staging).expect("remove failed staging fixture");
    }

    #[test]
    fn runtime_license_asset_identity_is_checked_before_atomic_promotion() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for field in ["source_relative_path", "sha256"] {
            let (mut runtime, entries) = approved_runtime_envelope_fixture();
            match field {
                "source_relative_path" => {
                    runtime.license_asset.source_relative_path = "missing.txt".into()
                }
                "sha256" => runtime.license_asset.sha256 = "0".repeat(64),
                _ => unreachable!("fixed test field"),
            }
            let archive = workspace.root.join(format!("license-{field}.zip"));
            let staging = workspace.root.join(format!("license-{field}.staging"));
            let destination = workspace.root.join(format!("license-{field}.destination"));
            write_owned_zip(&archive, &entries);

            let error =
                extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                    .expect_err("invalid source-controlled license asset must fail");

            assert_eq!(error.code, "license_asset_invalid");
            assert!(!destination.exists());
            assert!(!staging.join("LICENSE-MIT.txt").exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
        }
    }

    #[test]
    #[ignore = "requires an explicit operator-provided approved runtime archive path"]
    fn offline_approved_runtime_archive_validates_exact_envelope_and_extraction_plan() {
        let archive = PathBuf::from(
            std::env::var("LOCALCOMET_RUNTIME_ARCHIVE_VALIDATION_PATH")
                .expect("explicit archive validation path"),
        );
        let runtime = embedded_runtime();
        assert_eq!(
            fs::metadata(&archive)
                .expect("runtime archive metadata")
                .len(),
            18_007_324
        );
        assert_eq!(
            sha256_file(&archive, None).expect("hash approved runtime archive"),
            "01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89"
        );
        assert_eq!(runtime.archive_members.len(), 51);
        assert_eq!(runtime.required_files.len(), 30);

        let workspace = TestWorkspace::new();
        let staging = workspace.root.join("approved-runtime.staging");
        let destination = workspace
            .roots()
            .runtime_root
            .join(&runtime.managed_relative_path);
        fs::create_dir_all(destination.parent().expect("runtime destination parent"))
            .expect("create temporary runtime root");
        extract_and_install_runtime(
            &archive,
            &staging,
            &destination,
            &runtime,
            &AtomicBool::new(false),
        )
        .expect("approved runtime archive envelope and extraction plan");

        let mut expected = runtime
            .required_files
            .iter()
            .map(|file| file.relative_path.to_ascii_lowercase())
            .collect::<BTreeSet<_>>();
        expected.insert(
            runtime
                .license_asset
                .destination_relative_path
                .to_ascii_lowercase(),
        );
        assert_eq!(top_level_names(&destination), expected);
        assert!(!staging.exists());
        for skipped in runtime.archive_members.iter().filter(|member| {
            member.disposition == RuntimeArchiveMemberDisposition::RecognizedNotInstalled
        }) {
            assert!(!destination.join(&skipped.relative_path).exists());
        }
    }

    #[test]
    fn runtime_failure_codes_map_to_distinct_bounded_stages() {
        for (code, expected) in [
            ("download_failed", AcquisitionFailureStage::Transfer),
            ("size_mismatch", AcquisitionFailureStage::SizeVerification),
            ("hash_mismatch", AcquisitionFailureStage::HashVerification),
            (
                "invalid_runtime_archive",
                AcquisitionFailureStage::ArchiveValidation,
            ),
            (
                "staging_write_failed",
                AcquisitionFailureStage::StagingExtraction,
            ),
            (
                "atomic_install_failed",
                AcquisitionFailureStage::AtomicPromotion,
            ),
            (
                "post_install_validation_failed",
                AcquisitionFailureStage::PostInstallValidation,
            ),
        ] {
            assert_eq!(
                acquisition_failure_stage(code),
                expected,
                "stage for {code}"
            );
        }
    }

    #[test]
    fn terminal_runtime_failure_is_persisted_before_owned_cleanup() {
        let (_workspace, manager, trust) = test_manager();
        let mut artifact = trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved runtime");
        let expected_bytes = {
            let ApprovedDownloadArtifact::Runtime(runtime) = &mut artifact else {
                panic!("test runtime must be a runtime artifact");
            };
            runtime.acquisition.primary_url =
                "https://assets.example.test/runtime.zip?signed-token=must-not-persist".into();
            runtime.acquisition.expected_bytes
        };

        let job_id = register_job(&manager, TEST_RUNTIME_ID, expected_bytes, expected_bytes);
        let acquisition_root = trust.acquisition_root().expect("acquisition root");
        let partial = acquisition_root.join(format!("{job_id}.partial"));
        let staging = acquisition_root.join(format!("{job_id}.runtime-staging"));
        fs::write(&partial, b"runtime archive").expect("write owned partial");
        fs::create_dir(&staging).expect("create owned staging");
        fs::write(staging.join("member"), b"staging data").expect("write staging data");

        manager.persist_terminal_failure_before_cleanup(
            &job_id,
            &artifact,
            &AcquisitionError::new("staging_write_failed"),
        );

        let events = read_failure_events(&trust);
        assert_eq!(events.len(), 2);
        assert_eq!(events[0]["schema_version"], 1);
        assert_eq!(events[0]["artifact_kind"], "runtime");
        assert_eq!(events[0]["artifact_id"], TEST_RUNTIME_ID);
        assert_eq!(events[0]["terminal_status"], "failed");
        assert_eq!(events[0]["stage"], "staging_extraction");
        assert_eq!(events[0]["error_code"], "staging_write_failed");
        assert_eq!(events[0]["downloaded_bytes"], expected_bytes);
        assert_eq!(events[0]["cleanup_complete"], false);
        assert_eq!(events[0]["final_artifact_exists"], false);
        assert_eq!(events[1]["cleanup_complete"], true);
        assert!(!partial.exists());
        assert!(!staging.exists());
        assert!(!trust
            .download_destination(&artifact)
            .expect("runtime destination")
            .exists());

        let event_text =
            fs::read_to_string(trust.acquisition_event_log_path().expect("diagnostic path"))
                .expect("read diagnostic event text");
        assert!(!event_text.contains("signed-token"));
        assert!(!event_text.contains("assets.example.test"));
    }

    #[test]
    fn runtime_envelope_failure_diagnostic_records_only_bounded_member_context() {
        let (_workspace, manager, trust) = test_manager();
        let artifact = trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved runtime");
        let job_id = register_job(&manager, TEST_RUNTIME_ID, 7, 7);
        manager.persist_terminal_failure_before_cleanup(
            &job_id,
            &artifact,
            &AcquisitionError::new("unexpected_runtime_member")
                .archive_member("unknown.exe".into(), None)
                .archive_member_counts(51, 52),
        );

        let events = read_failure_events(&trust);
        assert_eq!(events[0]["stage"], "archive_validation");
        assert_eq!(events[0]["error_code"], "unexpected_runtime_member");
        assert_eq!(events[0]["archive_member"], "unknown.exe");
        assert!(events[0]["archive_disposition"].is_null());
        assert_eq!(events[0]["expected_member_count"], 51);
        assert_eq!(events[0]["observed_member_count"], 52);
        assert_eq!(events[1]["cleanup_complete"], true);
    }

    #[test]
    fn completed_job_does_not_emit_a_terminal_failure_event() {
        let (_workspace, manager, trust) = test_manager();
        let job_id = register_job(&manager, TEST_RUNTIME_ID, 7, 7);

        manager.complete(&job_id, ArtifactDownloadLifecycle::Completed, None);

        assert!(!trust
            .acquisition_event_log_path()
            .expect("diagnostic path")
            .exists());
    }

    #[test]
    fn terminal_event_uses_catalog_identity_and_backend_failure_values() {
        let (workspace, manager, trust) = test_manager();
        let artifact = trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved runtime");
        let job_id = register_job(&manager, TEST_RUNTIME_ID, 7, 3);
        let normal_profile_event = workspace
            .root
            .join("normal-profile")
            .join("LocalComet")
            .join("logs")
            .join("acquisition-events.jsonl");
        fs::create_dir_all(normal_profile_event.parent().expect("normal log parent"))
            .expect("create normal log parent");
        fs::write(&normal_profile_event, b"normal-profile-sentinel\n")
            .expect("write normal profile sentinel");
        {
            let mut registry = manager.jobs.lock().expect("download registry");
            registry
                .jobs
                .get_mut(&job_id)
                .expect("registered job")
                .state
                .artifact_id = "frontend-forged-artifact".into();
        }

        manager.persist_terminal_failure_before_cleanup(
            &job_id,
            &artifact,
            &AcquisitionError::new("atomic_install_failed"),
        );

        let events = read_failure_events(&trust);
        assert_eq!(events[0]["artifact_id"], TEST_RUNTIME_ID);
        assert_eq!(events[0]["stage"], "atomic_promotion");
        assert_eq!(events[0]["error_code"], "atomic_install_failed");
        assert_eq!(events[0]["downloaded_bytes"], 3);
        assert!(!events[0].to_string().contains("frontend-forged-artifact"));
        assert_eq!(
            fs::read_to_string(normal_profile_event).expect("read normal profile sentinel"),
            "normal-profile-sentinel\n"
        );
    }

    #[test]
    fn owned_partial_cleanup_never_targets_an_unrelated_file() {
        let (workspace, manager, trust) = test_manager();
        let root = trust.acquisition_root().expect("acquisition root");
        let job_id = "a".repeat(64);
        let owned = root.join(format!("{job_id}.partial"));
        let unrelated = root.join("notes.partial");
        fs::write(&owned, b"partial").expect("write owned partial");
        fs::write(&unrelated, b"keep").expect("write unrelated file");

        manager.remove_job_partial(&job_id);

        assert!(!owned.exists());
        assert!(unrelated.exists());
        drop(workspace);
    }

    #[test]
    fn cancellation_removes_only_the_active_job_partial() {
        let (_workspace, manager, trust) = test_manager();
        let root = trust.acquisition_root().expect("acquisition root");
        let job_id = "c".repeat(64);
        let partial = root.join(format!("{job_id}.partial"));
        let unrelated = root.join("user-model.gguf.partial");
        fs::write(&partial, b"partial").expect("write owned partial");
        fs::write(&unrelated, b"keep").expect("write unrelated partial");

        let artifact = trust
            .approved_download_artifact(TEST_MODEL_ID)
            .expect("approved model");
        manager.run_job(job_id, artifact, Arc::new(AtomicBool::new(true)));

        assert!(!partial.exists());
        assert!(unrelated.exists());
    }

    #[test]
    fn stale_cleanup_only_removes_owned_job_partials() {
        let (_workspace, manager, trust) = test_manager();
        let root = trust.acquisition_root().expect("acquisition root");
        let owned = root.join(format!("{}.partial", "b".repeat(64)));
        let unrelated = root.join("user-model.gguf.partial");
        fs::write(&owned, b"stale").expect("write stale partial");
        fs::write(&unrelated, b"keep").expect("write unrelated partial");

        manager.cleanup_stale_partials();

        assert!(!owned.exists());
        assert!(unrelated.exists());
    }

    #[test]
    fn start_reuses_valid_artifact_and_rejects_conflicting_or_unknown_artifacts() {
        let (_workspace, manager, trust) = test_manager();
        let confirmation = manager
            .start(TEST_RUNTIME_ID, false)
            .expect_err("require download confirmation");
        assert_eq!(confirmation.code, "confirmation_required");
        let package = trust.roots().runtime_root.join(TEST_RUNTIME_ID);
        fs::create_dir_all(&package).expect("create runtime package");
        fs::write(package.join("llama-server.exe"), TEST_RUNTIME_BYTES)
            .expect("write validated runtime");
        let runtime = match trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved test runtime")
        {
            ApprovedDownloadArtifact::Runtime(runtime) => runtime,
            ApprovedDownloadArtifact::Model(_) => {
                unreachable!("test runtime must remain a runtime")
            }
        };
        let license_bytes = source_controlled_runtime_license_bytes(&runtime.license_asset)
            .expect("test runtime license asset");
        fs::write(
            package.join(runtime.license_asset.destination_relative_path),
            license_bytes,
        )
        .expect("write validated runtime license");

        let reused = manager
            .start(TEST_RUNTIME_ID, true)
            .expect("reuse valid runtime");
        assert_eq!(reused.lifecycle, ArtifactDownloadLifecycle::Completed);
        assert_eq!(reused.received_bytes, reused.expected_bytes);
        assert_eq!(reused.percent, Some(100));

        let model = trust
            .approved_download_artifact(TEST_MODEL_ID)
            .expect("approved model");
        let model_destination = trust
            .download_destination(&model)
            .expect("model destination");
        fs::create_dir_all(model_destination.parent().expect("model parent"))
            .expect("create model parent");
        fs::write(&model_destination, b"conflicting").expect("write conflicting model");

        let conflict = manager
            .start(TEST_MODEL_ID, true)
            .expect_err("reject conflicting model");
        assert_eq!(conflict.code, "conflicting_installed_artifact");
        let unknown = manager
            .start("unknown-artifact", true)
            .expect_err("reject unknown artifact");
        assert_eq!(unknown.code, "unknown_artifact");
    }

    #[test]
    fn duplicate_job_is_returned_and_terminal_state_is_written_once() {
        let (_workspace, manager, _trust) = test_manager();
        let state = manager.new_state(
            TEST_RUNTIME_ID,
            7,
            ArtifactDownloadLifecycle::AwaitingConfirmation,
        );
        let job_id = state.job_id.clone();
        {
            let mut registry = manager.jobs.lock().expect("download registry");
            registry
                .active_by_artifact
                .insert(TEST_RUNTIME_ID.into(), job_id.clone());
            registry.jobs.insert(
                job_id.clone(),
                DownloadJob {
                    state: state.clone(),
                    cancel_requested: Arc::new(AtomicBool::new(false)),
                },
            );
        }

        let duplicate = manager
            .start(TEST_RUNTIME_ID, true)
            .expect("return existing download job");
        assert_eq!(duplicate.job_id, job_id);
        manager.complete(&job_id, ArtifactDownloadLifecycle::Cancelled, None);
        manager.complete(&job_id, ArtifactDownloadLifecycle::Completed, None);

        assert_eq!(
            manager.get(&job_id).expect("completed job").lifecycle,
            ArtifactDownloadLifecycle::Cancelled
        );
        assert!(!manager
            .jobs
            .lock()
            .expect("download registry")
            .active_by_artifact
            .contains_key(TEST_RUNTIME_ID));
    }
}
