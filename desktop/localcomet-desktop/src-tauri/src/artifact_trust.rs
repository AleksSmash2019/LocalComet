use crate::control_plane::BridgeError;
use serde::de::{MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::State;

#[cfg(windows)]
use std::os::windows::fs::{MetadataExt, OpenOptionsExt};

const CATALOG_BYTES: &[u8] = include_bytes!("../resources/localcomet/approved-artifacts.v1.json");
const CATALOG_ID: &str = "localcomet-approved-artifacts";
const SCHEMA_VERSION: u32 = 1;
const MAX_ARTIFACTS: usize = 32;
const MAX_REQUIRED_FILES: usize = 128;
const MAX_RUNTIME_ARCHIVE_BYTES: u64 = 4 * 1024 * 1024 * 1024;
const MAX_MODEL_BYTES: u64 = 128 * 1024 * 1024 * 1024;
const MODEL_ROOT_SENTINEL: &str = "<MANAGED_MODEL_ROOT>";
const INTERNAL_BOOTSTRAP_PURPOSE: &str = "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION";

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CatalogStatus {
    ApprovedInternalBootstrap,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeFile {
    pub relative_path: String,
    pub bytes: u64,
    pub sha256: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeArtifact {
    pub runtime_id: String,
    pub provider: String,
    pub release_tag: String,
    pub platform: String,
    pub architecture: String,
    pub variant: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub archive_format: String,
    pub managed_relative_path: String,
    pub executable_relative_path: String,
    pub required_files: Vec<ApprovedRuntimeFile>,
    pub permitted_bind_scope: String,
    pub supported_api_protocol: String,
    pub license_id: String,
    pub public_distribution: bool,
    pub status: CatalogStatus,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedModelArtifact {
    pub model_id: String,
    pub provider: String,
    pub family: String,
    pub display_name: String,
    pub format: String,
    pub quantization: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub license_id: String,
    pub compatible_runtime_ids: Vec<String>,
    pub managed_relative_path: String,
    pub public_distribution: bool,
    pub installer_bundled: bool,
    pub bootstrap_purpose: String,
    pub status: CatalogStatus,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedArtifactCatalog {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub runtimes: Vec<ApprovedRuntimeArtifact>,
    pub models: Vec<ApprovedModelArtifact>,
}

#[derive(Clone, Debug)]
pub(crate) struct ManagedArtifactRoots {
    pub app_data_root: PathBuf,
    pub runtime_root: PathBuf,
    pub model_root: PathBuf,
    pub state_root: PathBuf,
}

impl ManagedArtifactRoots {
    pub(crate) fn from_local_data_dir(local_data_dir: &Path) -> Self {
        let localcomet = local_data_dir.join("LocalComet");
        Self {
            app_data_root: local_data_dir.to_path_buf(),
            runtime_root: localcomet.join("runtimes").join("llama.cpp"),
            model_root: localcomet.join("models"),
            state_root: localcomet.join("runtime-state"),
        }
    }
}

#[derive(Debug)]
pub struct ArtifactTrustError {
    code: &'static str,
    message: String,
}

impl ArtifactTrustError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        let message = message.into();
        let safe: String = message
            .chars()
            .filter(|character| !character.is_control())
            .take(240)
            .collect();
        Self {
            code,
            message: safe,
        }
    }
}

impl From<ArtifactTrustError> for BridgeError {
    fn from(value: ArtifactTrustError) -> Self {
        BridgeError {
            code: value.code.into(),
            message: value.message,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactKind {
    Runtime,
    Model,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InstallationStatus {
    NotInstalled,
    Valid,
    BytesMismatch,
    HashMismatch,
    InvalidPath,
    InvalidFormat,
    MissingRequiredFile,
    UnexpectedFile,
    IoError,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CompatibilityStatus {
    Compatible,
    NoCompatibleRuntimeInstalled,
    IncompatibleRuntimeInstalled,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelReadiness {
    Ready,
    ModelNotInstalled,
    ModelInvalid,
    RuntimeNotInstalled,
    RuntimeInvalid,
    Incompatible,
}

#[derive(Clone, Debug, Serialize)]
pub struct ApprovedRuntimeSummary {
    pub runtime_id: String,
    pub provider: String,
    pub release_tag: String,
    pub platform: String,
    pub architecture: String,
    pub variant: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub archive_format: String,
    pub permitted_bind_scope: String,
    pub supported_api_protocol: String,
    pub license_id: String,
    pub public_distribution: bool,
    pub status: CatalogStatus,
    pub installation_status: InstallationStatus,
}

#[derive(Clone, Debug, Serialize)]
pub struct ApprovedModelSummary {
    pub model_id: String,
    pub provider: String,
    pub family: String,
    pub display_name: String,
    pub format: String,
    pub quantization: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub license_id: String,
    pub compatible_runtime_ids: Vec<String>,
    pub public_distribution: bool,
    pub installer_bundled: bool,
    pub bootstrap_purpose: String,
    pub status: CatalogStatus,
    pub installation_status: InstallationStatus,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeCatalog {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub runtimes: Vec<ApprovedRuntimeSummary>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedModelCatalog {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub engine: &'static str,
    pub model_root: &'static str,
    pub models: Vec<ApprovedModelSummary>,
    pub maximum_models: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct ArtifactValidationSummary {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub artifact_id: String,
    pub kind: ArtifactKind,
    pub catalog_status: CatalogStatus,
    pub installation_status: InstallationStatus,
    pub expected_bytes: u64,
    pub expected_sha256: String,
    pub observed_bytes: Option<u64>,
    pub observed_sha256: Option<String>,
    pub validation_code: String,
    pub verified_unix_ms: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedInstalledArtifacts {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub artifacts: Vec<ArtifactValidationSummary>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ModelReadinessSummary {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub model_id: String,
    pub model_status: InstallationStatus,
    pub compatible_runtime_ids: Vec<String>,
    pub selected_runtime_id: Option<String>,
    pub runtime_status: Option<InstallationStatus>,
    pub compatibility: CompatibilityStatus,
    pub readiness: ModelReadiness,
    pub launchable: bool,
}

#[derive(Debug)]
struct ValidationOutcome {
    status: InstallationStatus,
    observed_bytes: Option<u64>,
    observed_sha256: Option<String>,
    code: &'static str,
}

impl ValidationOutcome {
    fn not_installed() -> Self {
        Self {
            status: InstallationStatus::NotInstalled,
            observed_bytes: None,
            observed_sha256: None,
            code: "not_installed",
        }
    }
}

#[derive(Debug)]
pub(crate) struct ValidatedRuntimeModel {
    pub runtime_id: String,
    pub runtime_release_tag: String,
    pub package_dir: PathBuf,
    pub executable: PathBuf,
    pub model_id: String,
    pub model_display_name: String,
    pub model_path: PathBuf,
    pub model_handle: File,
    pub runtime_handles: Vec<File>,
}

pub struct ArtifactTrustService {
    catalog: ApprovedArtifactCatalog,
    catalog_digest: String,
    roots: ManagedArtifactRoots,
}

impl ArtifactTrustService {
    pub fn production(local_data_dir: &Path) -> Result<Self, ArtifactTrustError> {
        Self::from_catalog_bytes(
            CATALOG_BYTES,
            ManagedArtifactRoots::from_local_data_dir(local_data_dir),
        )
    }

    fn from_catalog_bytes(
        bytes: &[u8],
        roots: ManagedArtifactRoots,
    ) -> Result<Self, ArtifactTrustError> {
        let catalog = parse_catalog(bytes)?;
        validate_catalog(&catalog)?;
        validate_canonical_catalog_bytes(bytes, &catalog)?;
        Ok(Self {
            catalog,
            catalog_digest: sha256_bytes(bytes),
            roots,
        })
    }

    pub(crate) fn roots(&self) -> &ManagedArtifactRoots {
        &self.roots
    }

    pub fn runtime_catalog(&self) -> ManagedRuntimeCatalog {
        ManagedRuntimeCatalog {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            runtimes: self
                .catalog
                .runtimes
                .iter()
                .map(|runtime| ApprovedRuntimeSummary {
                    runtime_id: runtime.runtime_id.clone(),
                    provider: runtime.provider.clone(),
                    release_tag: runtime.release_tag.clone(),
                    platform: runtime.platform.clone(),
                    architecture: runtime.architecture.clone(),
                    variant: runtime.variant.clone(),
                    upstream_repository: runtime.upstream_repository.clone(),
                    upstream_revision: runtime.upstream_revision.clone(),
                    asset_filename: runtime.asset_filename.clone(),
                    asset_bytes: runtime.asset_bytes,
                    asset_sha256: runtime.asset_sha256.clone(),
                    archive_format: runtime.archive_format.clone(),
                    permitted_bind_scope: runtime.permitted_bind_scope.clone(),
                    supported_api_protocol: runtime.supported_api_protocol.clone(),
                    license_id: runtime.license_id.clone(),
                    public_distribution: runtime.public_distribution,
                    status: runtime.status.clone(),
                    installation_status: self.validate_runtime(runtime).status,
                })
                .collect(),
        }
    }

    pub fn model_catalog(&self) -> ManagedModelCatalog {
        ManagedModelCatalog {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            engine: "llama.cpp",
            model_root: MODEL_ROOT_SENTINEL,
            models: self
                .catalog
                .models
                .iter()
                .map(|model| ApprovedModelSummary {
                    model_id: model.model_id.clone(),
                    provider: model.provider.clone(),
                    family: model.family.clone(),
                    display_name: model.display_name.clone(),
                    format: model.format.clone(),
                    quantization: model.quantization.clone(),
                    upstream_repository: model.upstream_repository.clone(),
                    upstream_revision: model.upstream_revision.clone(),
                    asset_filename: model.asset_filename.clone(),
                    asset_bytes: model.asset_bytes,
                    asset_sha256: model.asset_sha256.clone(),
                    license_id: model.license_id.clone(),
                    compatible_runtime_ids: model.compatible_runtime_ids.clone(),
                    public_distribution: model.public_distribution,
                    installer_bundled: model.installer_bundled,
                    bootstrap_purpose: model.bootstrap_purpose.clone(),
                    status: model.status.clone(),
                    installation_status: self.validate_model(model).status,
                })
                .collect(),
            maximum_models: MAX_ARTIFACTS,
        }
    }

    pub fn installed_artifacts(&self) -> ManagedInstalledArtifacts {
        let mut artifacts = Vec::new();
        for runtime in &self.catalog.runtimes {
            artifacts.push(self.runtime_validation_summary(runtime));
        }
        for model in &self.catalog.models {
            artifacts.push(self.model_validation_summary(model));
        }
        ManagedInstalledArtifacts {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            artifacts,
        }
    }

    pub fn artifact_validation_status(
        &self,
        artifact_id: &str,
    ) -> Result<ArtifactValidationSummary, ArtifactTrustError> {
        validate_artifact_id(artifact_id)?;
        if let Some(runtime) = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == artifact_id)
        {
            return Ok(self.runtime_validation_summary(runtime));
        }
        if let Some(model) = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == artifact_id)
        {
            return Ok(self.model_validation_summary(model));
        }
        Err(ArtifactTrustError::new(
            "unknown_artifact",
            "unknown approved artifact id",
        ))
    }

    pub fn model_readiness(
        &self,
        model_id: &str,
    ) -> Result<ModelReadinessSummary, ArtifactTrustError> {
        validate_artifact_id(model_id)?;
        let model = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == model_id)
            .ok_or_else(|| ArtifactTrustError::new("unknown_artifact", "unknown model id"))?;
        let model_outcome = self.validate_model(model);
        let mut selected_runtime_id = None;
        let mut selected_runtime_status = None;
        let mut saw_invalid_runtime = false;
        for runtime_id in &model.compatible_runtime_ids {
            let runtime = self
                .catalog
                .runtimes
                .iter()
                .find(|runtime| &runtime.runtime_id == runtime_id)
                .ok_or_else(|| {
                    ArtifactTrustError::new("invalid_catalog", "unknown compatible runtime")
                })?;
            let outcome = self.validate_runtime(runtime);
            if outcome.status == InstallationStatus::Valid {
                selected_runtime_id = Some(runtime.runtime_id.clone());
                selected_runtime_status = Some(outcome.status);
                break;
            }
            if outcome.status != InstallationStatus::NotInstalled {
                saw_invalid_runtime = true;
            }
            if selected_runtime_status.is_none()
                || (selected_runtime_status == Some(InstallationStatus::NotInstalled)
                    && outcome.status != InstallationStatus::NotInstalled)
            {
                selected_runtime_status = Some(outcome.status);
            }
        }
        let incompatible_runtime_installed = selected_runtime_id.is_none()
            && self.catalog.runtimes.iter().any(|runtime| {
                !model
                    .compatible_runtime_ids
                    .iter()
                    .any(|runtime_id| runtime_id == &runtime.runtime_id)
                    && self.validate_runtime(runtime).status == InstallationStatus::Valid
            });
        let compatibility = if selected_runtime_id.is_some() {
            CompatibilityStatus::Compatible
        } else if incompatible_runtime_installed {
            CompatibilityStatus::IncompatibleRuntimeInstalled
        } else {
            CompatibilityStatus::NoCompatibleRuntimeInstalled
        };
        let (readiness, launchable) = match model_outcome.status {
            InstallationStatus::NotInstalled => (ModelReadiness::ModelNotInstalled, false),
            InstallationStatus::Valid if selected_runtime_id.is_some() => {
                (ModelReadiness::Ready, true)
            }
            InstallationStatus::Valid if saw_invalid_runtime => {
                (ModelReadiness::RuntimeInvalid, false)
            }
            InstallationStatus::Valid if incompatible_runtime_installed => {
                (ModelReadiness::Incompatible, false)
            }
            InstallationStatus::Valid => (ModelReadiness::RuntimeNotInstalled, false),
            _ => (ModelReadiness::ModelInvalid, false),
        };
        Ok(ModelReadinessSummary {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            model_id: model.model_id.clone(),
            model_status: model_outcome.status,
            compatible_runtime_ids: model.compatible_runtime_ids.clone(),
            selected_runtime_id,
            runtime_status: selected_runtime_status,
            compatibility,
            readiness,
            launchable,
        })
    }

    pub(crate) fn resolve_launch(
        &self,
        model_id: &str,
    ) -> Result<ValidatedRuntimeModel, ArtifactTrustError> {
        let readiness = self.model_readiness(model_id)?;
        if !readiness.launchable {
            return Err(ArtifactTrustError::new(
                "artifact_not_ready",
                "approved runtime/model pair is not ready",
            ));
        }
        let model = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == model_id)
            .ok_or_else(|| ArtifactTrustError::new("unknown_artifact", "unknown model id"))?;
        let runtime_id = readiness
            .selected_runtime_id
            .ok_or_else(|| ArtifactTrustError::new("artifact_not_ready", "runtime unavailable"))?;
        let runtime = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == runtime_id)
            .ok_or_else(|| ArtifactTrustError::new("invalid_catalog", "runtime unavailable"))?;
        let package_dir =
            resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path)?;
        let executable = resolve_contained(&package_dir, &runtime.executable_relative_path)?;
        let model_path = resolve_contained(&self.roots.model_root, &model.managed_relative_path)?;
        let model_handle = open_model_guard(&model_path)?;
        let mut runtime_handles = Vec::with_capacity(runtime.required_files.len());
        for required in &runtime.required_files {
            let path = resolve_contained(&package_dir, &required.relative_path)?;
            runtime_handles.push(open_runtime_guard(&path)?);
        }
        let model_recheck = self.validate_model(model);
        if model_recheck.status != InstallationStatus::Valid {
            return Err(ArtifactTrustError::new(
                "artifact_changed",
                "model identity changed before launch",
            ));
        }
        let runtime_recheck = self.validate_runtime(runtime);
        if runtime_recheck.status != InstallationStatus::Valid {
            return Err(ArtifactTrustError::new(
                "artifact_changed",
                "runtime identity changed before launch",
            ));
        }
        Ok(ValidatedRuntimeModel {
            runtime_id: runtime.runtime_id.clone(),
            runtime_release_tag: runtime.release_tag.clone(),
            package_dir,
            executable,
            model_id: model.model_id.clone(),
            model_display_name: model.display_name.clone(),
            model_path,
            model_handle,
            runtime_handles,
        })
    }

    pub(crate) fn has_valid_runtime(&self) -> bool {
        self.catalog
            .runtimes
            .iter()
            .any(|runtime| self.validate_runtime(runtime).status == InstallationStatus::Valid)
    }

    fn runtime_validation_summary(
        &self,
        runtime: &ApprovedRuntimeArtifact,
    ) -> ArtifactValidationSummary {
        let outcome = self.validate_runtime(runtime);
        self.validation_summary(
            &runtime.runtime_id,
            ArtifactKind::Runtime,
            runtime.status.clone(),
            runtime.asset_bytes,
            &runtime.asset_sha256,
            outcome,
        )
    }

    fn model_validation_summary(&self, model: &ApprovedModelArtifact) -> ArtifactValidationSummary {
        let outcome = self.validate_model(model);
        self.validation_summary(
            &model.model_id,
            ArtifactKind::Model,
            model.status.clone(),
            model.asset_bytes,
            &model.asset_sha256,
            outcome,
        )
    }

    fn validation_summary(
        &self,
        artifact_id: &str,
        kind: ArtifactKind,
        catalog_status: CatalogStatus,
        expected_bytes: u64,
        expected_sha256: &str,
        outcome: ValidationOutcome,
    ) -> ArtifactValidationSummary {
        ArtifactValidationSummary {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            artifact_id: artifact_id.to_string(),
            kind,
            catalog_status,
            installation_status: outcome.status,
            expected_bytes,
            expected_sha256: expected_sha256.to_string(),
            observed_bytes: outcome.observed_bytes,
            observed_sha256: outcome.observed_sha256,
            validation_code: outcome.code.into(),
            verified_unix_ms: now_unix_ms(),
        }
    }

    fn validate_runtime(&self, runtime: &ApprovedRuntimeArtifact) -> ValidationOutcome {
        let package_dir =
            match resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path) {
                Ok(path) => path,
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::InvalidPath,
                        observed_bytes: None,
                        observed_sha256: None,
                        code: "invalid_path",
                    }
                }
            };
        if !package_dir.exists() {
            return ValidationOutcome::not_installed();
        }
        if ensure_existing_safe_path(
            &self.roots.app_data_root,
            &self.roots.runtime_root,
            &package_dir,
            true,
        )
        .is_err()
        {
            return ValidationOutcome {
                status: InstallationStatus::InvalidPath,
                observed_bytes: None,
                observed_sha256: None,
                code: "invalid_path",
            };
        }
        let mut listed = BTreeSet::new();
        for required in &runtime.required_files {
            listed.insert(required.relative_path.to_ascii_lowercase());
            let file_path = match resolve_contained(&package_dir, &required.relative_path) {
                Ok(path) => path,
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::InvalidPath,
                        observed_bytes: None,
                        observed_sha256: None,
                        code: "invalid_path",
                    }
                }
            };
            let metadata = match file_path.metadata() {
                Ok(metadata) if metadata.is_file() => metadata,
                _ => {
                    return ValidationOutcome {
                        status: InstallationStatus::MissingRequiredFile,
                        observed_bytes: None,
                        observed_sha256: None,
                        code: "missing_required_file",
                    }
                }
            };
            if reject_reparse_point(&file_path).is_err() {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                };
            }
            if metadata.len() != required.bytes {
                return ValidationOutcome {
                    status: InstallationStatus::BytesMismatch,
                    observed_bytes: Some(metadata.len()),
                    observed_sha256: None,
                    code: "bytes_mismatch",
                };
            }
            match sha256_file(&file_path) {
                Ok(hash) if hash == required.sha256 => {}
                Ok(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::HashMismatch,
                        observed_bytes: Some(metadata.len()),
                        observed_sha256: None,
                        code: "hash_mismatch",
                    }
                }
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::IoError,
                        observed_bytes: Some(metadata.len()),
                        observed_sha256: None,
                        code: "io_error",
                    }
                }
            }
        }
        if reject_unlisted_runtime_files(&package_dir, &listed).is_err() {
            return ValidationOutcome {
                status: InstallationStatus::UnexpectedFile,
                observed_bytes: None,
                observed_sha256: None,
                code: "unexpected_file",
            };
        }
        ValidationOutcome {
            status: InstallationStatus::Valid,
            observed_bytes: None,
            observed_sha256: None,
            code: "valid",
        }
    }

    fn validate_model(&self, model: &ApprovedModelArtifact) -> ValidationOutcome {
        let path = match resolve_contained(&self.roots.model_root, &model.managed_relative_path) {
            Ok(path) => path,
            Err(_) => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                }
            }
        };
        if !path.exists() {
            return ValidationOutcome::not_installed();
        }
        if ensure_existing_safe_path(
            &self.roots.app_data_root,
            &self.roots.model_root,
            &path,
            false,
        )
        .is_err()
        {
            return ValidationOutcome {
                status: InstallationStatus::InvalidPath,
                observed_bytes: None,
                observed_sha256: None,
                code: "invalid_path",
            };
        }
        let metadata = match path.metadata() {
            Ok(metadata) if metadata.is_file() => metadata,
            _ => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                }
            }
        };
        if metadata.len() != model.asset_bytes {
            return ValidationOutcome {
                status: InstallationStatus::BytesMismatch,
                observed_bytes: Some(metadata.len()),
                observed_sha256: None,
                code: "bytes_mismatch",
            };
        }
        let mut magic = [0_u8; 4];
        match File::open(&path).and_then(|mut file| file.read_exact(&mut magic)) {
            Ok(()) if &magic == b"GGUF" => {}
            _ => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidFormat,
                    observed_bytes: Some(metadata.len()),
                    observed_sha256: None,
                    code: "invalid_format",
                }
            }
        }
        match sha256_file(&path) {
            Ok(hash) if hash == model.asset_sha256 => ValidationOutcome {
                status: InstallationStatus::Valid,
                observed_bytes: Some(metadata.len()),
                observed_sha256: Some(hash),
                code: "valid",
            },
            Ok(hash) => ValidationOutcome {
                status: InstallationStatus::HashMismatch,
                observed_bytes: Some(metadata.len()),
                observed_sha256: Some(hash),
                code: "hash_mismatch",
            },
            Err(_) => ValidationOutcome {
                status: InstallationStatus::IoError,
                observed_bytes: Some(metadata.len()),
                observed_sha256: None,
                code: "io_error",
            },
        }
    }
}

#[tauri::command]
pub fn managed_runtime_catalog(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> ManagedRuntimeCatalog {
    state.runtime_catalog()
}

#[tauri::command]
pub fn managed_model_catalog(state: State<'_, Arc<ArtifactTrustService>>) -> ManagedModelCatalog {
    state.model_catalog()
}

#[tauri::command]
pub fn managed_installed_artifacts(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> ManagedInstalledArtifacts {
    state.installed_artifacts()
}

#[tauri::command]
pub fn managed_artifact_validation_status(
    state: State<'_, Arc<ArtifactTrustService>>,
    artifact_id: String,
) -> Result<ArtifactValidationSummary, BridgeError> {
    state
        .artifact_validation_status(&artifact_id)
        .map_err(BridgeError::from)
}

#[tauri::command]
pub fn managed_model_readiness(
    state: State<'_, Arc<ArtifactTrustService>>,
    model_id: String,
) -> Result<ModelReadinessSummary, BridgeError> {
    state.model_readiness(&model_id).map_err(BridgeError::from)
}

fn parse_catalog(bytes: &[u8]) -> Result<ApprovedArtifactCatalog, ArtifactTrustError> {
    if bytes.starts_with(&[0xef, 0xbb, 0xbf]) {
        return Err(ArtifactTrustError::new("invalid_catalog", "BOM rejected"));
    }
    let mut deserializer = serde_json::Deserializer::from_slice(bytes);
    let unique = UniqueValue::deserialize(&mut deserializer)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog JSON rejected"))?;
    deserializer
        .end()
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog trailing data"))?;
    serde_json::from_value(unique.0)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog schema rejected"))
}

fn validate_canonical_catalog_bytes(
    bytes: &[u8],
    catalog: &ApprovedArtifactCatalog,
) -> Result<(), ArtifactTrustError> {
    let text = std::str::from_utf8(bytes)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog is not UTF-8"))?;
    if text.contains('\r')
        || !text.ends_with('\n')
        || text.ends_with("\n\n")
        || text.lines().any(|line| line.ends_with([' ', '\t']))
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "catalog serialization rejected",
        ));
    }
    let mut canonical = serde_json::to_string_pretty(catalog)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog serialization failed"))?;
    canonical.push('\n');
    if canonical.as_bytes() != bytes {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "catalog is not canonical",
        ));
    }
    Ok(())
}

fn validate_catalog(catalog: &ApprovedArtifactCatalog) -> Result<(), ArtifactTrustError> {
    if catalog.schema_version != SCHEMA_VERSION
        || catalog.catalog_id != CATALOG_ID
        || catalog.catalog_version.is_empty()
        || catalog.catalog_version.len() > 64
        || catalog.catalog_version.bytes().any(|byte| {
            !(byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'.' | b'-'))
        })
        || catalog.runtimes.is_empty()
        || catalog.runtimes.len() > MAX_ARTIFACTS
        || catalog.models.is_empty()
        || catalog.models.len() > MAX_ARTIFACTS
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "catalog header rejected",
        ));
    }
    ensure_sorted_unique(
        catalog
            .runtimes
            .iter()
            .map(|runtime| runtime.runtime_id.as_str()),
    )?;
    ensure_sorted_unique(catalog.models.iter().map(|model| model.model_id.as_str()))?;
    let runtime_ids: BTreeSet<&str> = catalog
        .runtimes
        .iter()
        .map(|runtime| runtime.runtime_id.as_str())
        .collect();
    let mut artifact_ids = BTreeSet::new();
    let mut filenames = BTreeMap::new();
    let mut runtime_locations = BTreeSet::new();
    let mut model_locations = BTreeSet::new();

    for runtime in &catalog.runtimes {
        validate_artifact_id(&runtime.runtime_id)?;
        if !artifact_ids.insert(runtime.runtime_id.as_str()) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "duplicate artifact id",
            ));
        }
        validate_required_texts(&[
            &runtime.provider,
            &runtime.release_tag,
            &runtime.upstream_repository,
            &runtime.upstream_revision,
            &runtime.license_id,
        ])?;
        if runtime.platform != "windows"
            || runtime.architecture != "x86-64"
            || runtime.variant != "cpu"
            || runtime.archive_format != "zip"
            || runtime.permitted_bind_scope != "loopback-only"
            || runtime.supported_api_protocol != "openai-compatible-v1"
            || runtime.public_distribution
            || runtime.asset_bytes == 0
            || runtime.asset_bytes > MAX_RUNTIME_ARCHIVE_BYTES
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime policy rejected",
            ));
        }
        validate_sha256(&runtime.asset_sha256)?;
        validate_filename(&runtime.asset_filename)?;
        validate_relative_windows_path(&runtime.managed_relative_path)?;
        insert_disjoint_managed_path(&mut runtime_locations, &runtime.managed_relative_path)?;
        validate_relative_windows_path(&runtime.executable_relative_path)?;
        if !runtime
            .executable_relative_path
            .to_ascii_lowercase()
            .ends_with(".exe")
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime executable extension rejected",
            ));
        }
        if runtime.required_files.is_empty() || runtime.required_files.len() > MAX_REQUIRED_FILES {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime file list rejected",
            ));
        }
        let mut file_paths = BTreeSet::new();
        let mut previous = None::<String>;
        let mut executable_found = false;
        for required in &runtime.required_files {
            validate_relative_windows_path(&required.relative_path)?;
            validate_sha256(&required.sha256)?;
            if required.bytes == 0 {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime file size rejected",
                ));
            }
            let folded = required.relative_path.to_ascii_lowercase();
            if previous
                .as_ref()
                .is_some_and(|value| value >= &folded || folded.starts_with(&format!("{value}/")))
                || !file_paths.insert(folded.clone())
            {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime files not sorted or unique",
                ));
            }
            previous = Some(folded);
            if required
                .relative_path
                .eq_ignore_ascii_case(&runtime.executable_relative_path)
            {
                executable_found = true;
            }
        }
        if !executable_found {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime executable identity missing",
            ));
        }
        insert_filename(
            &mut filenames,
            &runtime.asset_filename,
            &runtime.managed_relative_path,
        )?;
    }

    for model in &catalog.models {
        validate_artifact_id(&model.model_id)?;
        if !artifact_ids.insert(model.model_id.as_str()) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "duplicate artifact id",
            ));
        }
        validate_required_texts(&[
            &model.provider,
            &model.family,
            &model.display_name,
            &model.upstream_repository,
            &model.upstream_revision,
            &model.license_id,
        ])?;
        if model.format != "GGUF"
            || model.quantization != "Q4_K_M"
            || model.asset_bytes == 0
            || model.asset_bytes > MAX_MODEL_BYTES
            || model.public_distribution
            || model.installer_bundled
            || model.bootstrap_purpose != INTERNAL_BOOTSTRAP_PURPOSE
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "model policy rejected",
            ));
        }
        validate_sha256(&model.asset_sha256)?;
        validate_filename(&model.asset_filename)?;
        validate_relative_windows_path(&model.managed_relative_path)?;
        insert_disjoint_managed_path(&mut model_locations, &model.managed_relative_path)?;
        let managed_filename = model
            .managed_relative_path
            .rsplit('/')
            .next()
            .unwrap_or_default();
        if !model.asset_filename.to_ascii_lowercase().ends_with(".gguf")
            || !managed_filename.eq_ignore_ascii_case(&model.asset_filename)
            || model.compatible_runtime_ids.is_empty()
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "model path or compatibility rejected",
            ));
        }
        ensure_sorted_unique(
            model
                .compatible_runtime_ids
                .iter()
                .map(|runtime_id| runtime_id.as_str()),
        )?;
        for runtime_id in &model.compatible_runtime_ids {
            validate_artifact_id(runtime_id)?;
            if !runtime_ids.contains(runtime_id.as_str()) {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "unknown compatible runtime",
                ));
            }
        }
        insert_filename(
            &mut filenames,
            &model.asset_filename,
            &model.managed_relative_path,
        )?;
    }
    Ok(())
}

fn validate_required_texts(values: &[&str]) -> Result<(), ArtifactTrustError> {
    if values
        .iter()
        .any(|value| value.is_empty() || value.len() > 256 || value.contains('\0'))
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "required catalog field rejected",
        ));
    }
    Ok(())
}

fn validate_artifact_id(value: &str) -> Result<(), ArtifactTrustError> {
    if value.len() < 3
        || value.len() > 96
        || !value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        || value.bytes().any(|byte| {
            !(byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || matches!(byte, b'.' | b'_' | b'-'))
        })
    {
        return Err(ArtifactTrustError::new(
            "invalid_artifact_id",
            "artifact id rejected",
        ));
    }
    Ok(())
}

fn validate_sha256(value: &str) -> Result<(), ArtifactTrustError> {
    if value.len() != 64
        || value
            .bytes()
            .any(|byte| !(byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)))
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "SHA-256 rejected",
        ));
    }
    Ok(())
}

fn validate_filename(value: &str) -> Result<(), ArtifactTrustError> {
    validate_relative_windows_path(value)?;
    if value.contains('/') {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "artifact filename rejected",
        ));
    }
    Ok(())
}

fn validate_relative_windows_path(value: &str) -> Result<(), ArtifactTrustError> {
    if value.is_empty()
        || value.len() > 240
        || value.starts_with('/')
        || value.starts_with('\\')
        || value.contains('\\')
        || value.contains(':')
        || value.contains('\0')
        || value.ends_with('/')
    {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed relative path rejected",
        ));
    }
    let reserved = [
        "con", "prn", "aux", "nul", "clock$", "com1", "com2", "com3", "com4", "com5", "com6",
        "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8",
        "lpt9",
    ];
    for segment in value.split('/') {
        let lowered = segment.to_ascii_lowercase();
        let stem = lowered.split('.').next().unwrap_or("");
        if segment.is_empty()
            || segment == "."
            || segment == ".."
            || segment.ends_with([' ', '.'])
            || reserved.contains(&stem)
        {
            return Err(ArtifactTrustError::new(
                "invalid_path",
                "managed path segment rejected",
            ));
        }
    }
    Ok(())
}

fn ensure_sorted_unique<'a>(
    values: impl Iterator<Item = &'a str>,
) -> Result<(), ArtifactTrustError> {
    let mut previous = None::<&str>;
    for value in values {
        if previous.is_some_and(|prior| prior >= value) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "catalog IDs not sorted or unique",
            ));
        }
        previous = Some(value);
    }
    Ok(())
}

fn insert_filename(
    filenames: &mut BTreeMap<String, String>,
    filename: &str,
    relative_path: &str,
) -> Result<(), ArtifactTrustError> {
    let key = filename.to_ascii_lowercase();
    if let Some(existing) = filenames.insert(key, relative_path.to_ascii_lowercase()) {
        if existing != relative_path.to_ascii_lowercase() {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "conflicting artifact filename",
            ));
        }
    }
    Ok(())
}

fn insert_disjoint_managed_path(
    locations: &mut BTreeSet<String>,
    relative_path: &str,
) -> Result<(), ArtifactTrustError> {
    let folded = relative_path.to_ascii_lowercase();
    let nested_prefix = format!("{folded}/");
    if locations.iter().any(|existing| {
        existing == &folded
            || existing.starts_with(&nested_prefix)
            || folded.starts_with(&format!("{existing}/"))
    }) {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "managed artifact paths overlap",
        ));
    }
    locations.insert(folded);
    Ok(())
}

fn resolve_contained(root: &Path, relative: &str) -> Result<PathBuf, ArtifactTrustError> {
    validate_relative_windows_path(relative)?;
    let mut path = root.to_path_buf();
    for segment in relative.split('/') {
        path.push(segment);
    }
    if !path.starts_with(root) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path containment failed",
        ));
    }
    Ok(path)
}

fn ensure_existing_safe_path(
    trust_root: &Path,
    root: &Path,
    path: &Path,
    directory: bool,
) -> Result<(), ArtifactTrustError> {
    if !path.starts_with(root) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path escaped root",
        ));
    }
    let metadata = path
        .metadata()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed path unavailable"))?;
    if (directory && !metadata.is_dir()) || (!directory && !metadata.is_file()) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path type rejected",
        ));
    }
    reject_reparse_chain(trust_root, path)?;
    let canonical_root = root
        .canonicalize()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed root unavailable"))?;
    let canonical_path = path
        .canonicalize()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed path unavailable"))?;
    if !canonical_path.starts_with(&canonical_root) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path canonical escape",
        ));
    }
    Ok(())
}

fn reject_unlisted_runtime_files(
    package_dir: &Path,
    listed: &BTreeSet<String>,
) -> Result<(), ArtifactTrustError> {
    let mut stack = vec![package_dir.to_path_buf()];
    let mut visited = 0_usize;
    while let Some(directory) = stack.pop() {
        for entry in fs::read_dir(&directory)
            .map_err(|_| ArtifactTrustError::new("io_error", "runtime package unreadable"))?
        {
            let entry =
                entry.map_err(|_| ArtifactTrustError::new("io_error", "runtime scan failed"))?;
            visited += 1;
            if visited > 256 {
                return Err(ArtifactTrustError::new(
                    "invalid_runtime",
                    "runtime package entry limit exceeded",
                ));
            }
            let path = entry.path();
            reject_reparse_point(&path)?;
            let file_type = entry
                .file_type()
                .map_err(|_| ArtifactTrustError::new("io_error", "runtime entry unreadable"))?;
            if file_type.is_dir() {
                let relative = path
                    .strip_prefix(package_dir)
                    .map_err(|_| ArtifactTrustError::new("invalid_path", "runtime path escaped"))?
                    .to_string_lossy()
                    .replace('\\', "/")
                    .to_ascii_lowercase();
                let prefix = format!("{relative}/");
                if !listed.iter().any(|item| item.starts_with(&prefix)) {
                    return Err(ArtifactTrustError::new(
                        "unexpected_file",
                        "unapproved runtime directory",
                    ));
                }
                stack.push(path);
                continue;
            }
            let relative = path
                .strip_prefix(package_dir)
                .map_err(|_| ArtifactTrustError::new("invalid_path", "runtime path escaped"))?
                .to_string_lossy()
                .replace('\\', "/")
                .to_ascii_lowercase();
            if !file_type.is_file() || !listed.contains(&relative) {
                return Err(ArtifactTrustError::new(
                    "unexpected_file",
                    "unapproved runtime file",
                ));
            }
        }
    }
    Ok(())
}

fn reject_reparse_chain(root: &Path, path: &Path) -> Result<(), ArtifactTrustError> {
    let relative = path
        .strip_prefix(root)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed path escaped root"))?;
    reject_reparse_point(root)?;
    let mut current = root.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        reject_reparse_point(&current)?;
    }
    Ok(())
}

#[cfg(windows)]
fn reject_reparse_point(path: &Path) -> Result<(), ArtifactTrustError> {
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
    let metadata = fs::symlink_metadata(path)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "path metadata unavailable"))?;
    if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "reparse point rejected",
        ));
    }
    Ok(())
}

#[cfg(not(windows))]
fn reject_reparse_point(path: &Path) -> Result<(), ArtifactTrustError> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "path metadata unavailable"))?;
    if metadata.file_type().is_symlink() {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "symbolic link rejected",
        ));
    }
    Ok(())
}

#[cfg(windows)]
fn open_model_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    const GENERIC_READ: u32 = 0x8000_0000;
    const FILE_SHARE_READ: u32 = 0x0000_0001;
    OpenOptions::new()
        .read(true)
        .access_mode(GENERIC_READ)
        .share_mode(FILE_SHARE_READ)
        .open(path)
        .map_err(|_| ArtifactTrustError::new("model_locked", "model identity guard failed"))
}

#[cfg(windows)]
fn open_runtime_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    const GENERIC_READ: u32 = 0x8000_0000;
    const FILE_SHARE_READ: u32 = 0x0000_0001;
    OpenOptions::new()
        .read(true)
        .access_mode(GENERIC_READ)
        .share_mode(FILE_SHARE_READ)
        .open(path)
        .map_err(|_| ArtifactTrustError::new("runtime_locked", "runtime identity guard failed"))
}

#[cfg(not(windows))]
fn open_model_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    File::open(path)
        .map_err(|_| ArtifactTrustError::new("model_locked", "model identity guard failed"))
}

#[cfg(not(windows))]
fn open_runtime_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    File::open(path)
        .map_err(|_| ArtifactTrustError::new("runtime_locked", "runtime identity guard failed"))
}

fn sha256_file(path: &Path) -> Result<String, ArtifactTrustError> {
    let file = File::open(path)
        .map_err(|_| ArtifactTrustError::new("io_error", "hash input unavailable"))?;
    let mut reader = BufReader::with_capacity(1024 * 1024, file);
    let mut hasher = Sha256::new();
    let mut buffer = vec![0_u8; 1024 * 1024];
    loop {
        let count = reader
            .read(&mut buffer)
            .map_err(|_| ArtifactTrustError::new("io_error", "hash read failed"))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

struct UniqueValue(Value);

impl<'de> Deserialize<'de> for UniqueValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_any(UniqueValueVisitor)
    }
}

struct UniqueValueVisitor;

impl<'de> Visitor<'de> for UniqueValueVisitor {
    type Value = UniqueValue;

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("a duplicate-free JSON value")
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Bool(value)))
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Number(value.into())))
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Number(value.into())))
    }

    fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        serde_json::Number::from_f64(value)
            .map(Value::Number)
            .map(UniqueValue)
            .ok_or_else(|| E::custom("invalid number"))
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::String(value.to_string())))
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::String(value)))
    }

    fn visit_none<E>(self) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Null))
    }

    fn visit_unit<E>(self) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Null))
    }

    fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: Deserializer<'de>,
    {
        UniqueValue::deserialize(deserializer)
    }

    fn visit_seq<A>(self, mut sequence: A) -> Result<Self::Value, A::Error>
    where
        A: SeqAccess<'de>,
    {
        let mut values = Vec::new();
        while let Some(value) = sequence.next_element::<UniqueValue>()? {
            values.push(value.0);
        }
        Ok(UniqueValue(Value::Array(values)))
    }

    fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
    where
        A: MapAccess<'de>,
    {
        let mut values = serde_json::Map::new();
        while let Some((key, value)) = map.next_entry::<String, UniqueValue>()? {
            if values.insert(key, value.0).is_some() {
                return Err(serde::de::Error::custom("duplicate JSON key"));
            }
        }
        Ok(UniqueValue(Value::Object(values)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    const EMBEDDED_CATALOG_SHA256: &str =
        "e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c";
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
                "localcomet-artifact-trust-{}-{}-{sequence}",
                std::process::id(),
                now_unix_ms()
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

    fn test_runtime(runtime_id: &str, managed_path: &str) -> ApprovedRuntimeArtifact {
        ApprovedRuntimeArtifact {
            runtime_id: runtime_id.into(),
            provider: "test-provider".into(),
            release_tag: "b1".into(),
            platform: "windows".into(),
            architecture: "x86-64".into(),
            variant: "cpu".into(),
            upstream_repository: "test/runtime".into(),
            upstream_revision: "1111111111111111111111111111111111111111".into(),
            asset_filename: format!("{runtime_id}.zip"),
            asset_bytes: 7,
            asset_sha256: sha256_bytes(b"archive"),
            archive_format: "zip".into(),
            managed_relative_path: managed_path.into(),
            executable_relative_path: "llama-server.exe".into(),
            required_files: vec![ApprovedRuntimeFile {
                relative_path: "llama-server.exe".into(),
                bytes: TEST_RUNTIME_BYTES.len() as u64,
                sha256: sha256_bytes(TEST_RUNTIME_BYTES),
            }],
            permitted_bind_scope: "loopback-only".into(),
            supported_api_protocol: "openai-compatible-v1".into(),
            license_id: "MIT".into(),
            public_distribution: false,
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_model(compatible_runtime_ids: Vec<String>) -> ApprovedModelArtifact {
        ApprovedModelArtifact {
            model_id: "test-model".into(),
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
            license_id: "Apache-2.0".into(),
            compatible_runtime_ids,
            managed_relative_path: "test-model/test-model.gguf".into(),
            public_distribution: false,
            installer_bundled: false,
            bootstrap_purpose: INTERNAL_BOOTSTRAP_PURPOSE.into(),
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_catalog() -> ApprovedArtifactCatalog {
        ApprovedArtifactCatalog {
            schema_version: SCHEMA_VERSION,
            catalog_id: CATALOG_ID.into(),
            catalog_version: "1.0.0-test".into(),
            runtimes: vec![test_runtime("test-runtime", "test-runtime")],
            models: vec![test_model(vec!["test-runtime".into()])],
        }
    }

    fn canonical_bytes(catalog: &ApprovedArtifactCatalog) -> Vec<u8> {
        let mut text = serde_json::to_string_pretty(catalog).expect("serialize test catalog");
        text.push('\n');
        text.into_bytes()
    }

    fn service_for(
        catalog: &ApprovedArtifactCatalog,
        workspace: &TestWorkspace,
    ) -> ArtifactTrustService {
        ArtifactTrustService::from_catalog_bytes(&canonical_bytes(catalog), workspace.roots())
            .expect("valid test catalog")
    }

    fn install_runtime(
        workspace: &TestWorkspace,
        runtime: &ApprovedRuntimeArtifact,
        bytes: &[u8],
    ) -> PathBuf {
        let package = workspace
            .roots()
            .runtime_root
            .join(&runtime.managed_relative_path);
        fs::create_dir_all(&package).expect("create runtime package");
        let executable = package.join(&runtime.executable_relative_path);
        fs::write(&executable, bytes).expect("write runtime fixture");
        executable
    }

    fn install_model(
        workspace: &TestWorkspace,
        model: &ApprovedModelArtifact,
        bytes: &[u8],
    ) -> PathBuf {
        let path = workspace
            .roots()
            .model_root
            .join(model.managed_relative_path.split('/').collect::<PathBuf>());
        fs::create_dir_all(path.parent().expect("model parent")).expect("create model directory");
        fs::write(&path, bytes).expect("write model fixture");
        path
    }

    fn assert_catalog_invalid(catalog: &ApprovedArtifactCatalog) {
        assert!(validate_catalog(catalog).is_err());
    }

    #[test]
    fn embedded_catalog_is_canonical_and_exactly_pinned() {
        let workspace = TestWorkspace::new();
        let service = ArtifactTrustService::from_catalog_bytes(CATALOG_BYTES, workspace.roots())
            .expect("embedded catalog must be valid");
        assert_eq!(sha256_bytes(CATALOG_BYTES), EMBEDDED_CATALOG_SHA256);
        assert_eq!(service.catalog.runtimes.len(), 1);
        assert_eq!(service.catalog.models.len(), 1);

        let runtime = &service.catalog.runtimes[0];
        assert_eq!(runtime.runtime_id, "llama-cpp-windows-x86-64-cpu-bootstrap");
        assert_eq!(runtime.release_tag, "b10068");
        assert_eq!(
            runtime.upstream_revision,
            "571d0d540df04f25298d0e159e520d9fc62ed121"
        );
        assert_eq!(runtime.asset_bytes, 18_007_324);
        assert_eq!(
            runtime.asset_sha256,
            "01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89"
        );
        assert_eq!(runtime.required_files.len(), 31);

        let model = &service.catalog.models[0];
        assert_eq!(model.model_id, "qwen2.5-1.5b-instruct-q4-k-m");
        assert_eq!(
            model.upstream_revision,
            "91cad51170dc346986eccefdc2dd33a9da36ead9"
        );
        assert_eq!(model.asset_bytes, 1_117_320_736);
        assert_eq!(
            model.asset_sha256,
            "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
        );
    }

    #[test]
    fn parser_rejects_duplicate_keys_unknown_fields_and_noncanonical_bytes() {
        let duplicate = br#"{"schema_version":1,"schema_version":1}"#;
        assert!(parse_catalog(duplicate).is_err());

        let mut value = serde_json::to_value(test_catalog()).expect("catalog value");
        value
            .as_object_mut()
            .expect("catalog object")
            .insert("approval_override".into(), Value::Bool(true));
        assert!(serde_json::from_value::<ApprovedArtifactCatalog>(value).is_err());

        let catalog = test_catalog();
        let compact = serde_json::to_vec(&catalog).expect("compact catalog");
        assert!(validate_canonical_catalog_bytes(&compact, &catalog).is_err());
        let mut crlf = String::from_utf8(canonical_bytes(&catalog)).expect("catalog UTF-8");
        crlf = crlf.replace('\n', "\r\n");
        assert!(validate_canonical_catalog_bytes(crlf.as_bytes(), &catalog).is_err());
        let mut extra_newline = canonical_bytes(&catalog);
        extra_newline.push(b'\n');
        assert!(validate_canonical_catalog_bytes(&extra_newline, &catalog).is_err());
    }

    #[test]
    fn catalog_schema_rejects_all_authority_boundary_violations() {
        let baseline = test_catalog();

        let mut catalog = baseline.clone();
        catalog.schema_version = 2;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes.push(catalog.runtimes[0].clone());
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models.push(catalog.models[0].clone());
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].runtime_id = "../runtime".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].asset_sha256 = "ABC".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].asset_bytes = 0;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].managed_relative_path = "C:/runtime".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].executable_relative_path = "../llama-server.exe".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].managed_relative_path = "/model/test-model.gguf".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].provider.clear();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].compatible_runtime_ids = vec!["unknown-runtime".into()];
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        let mut conflicting = catalog.models[0].clone();
        conflicting.model_id = "zzz-model".into();
        conflicting.managed_relative_path = "zzz-model/test-model.gguf".into();
        catalog.models.push(conflicting);
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].architecture = "arm64".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].public_distribution = true;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline;
        catalog.runtimes.clear();
        assert_catalog_invalid(&catalog);
    }

    #[test]
    fn relative_windows_paths_reject_absolute_drive_traversal_and_reserved_forms() {
        for rejected in [
            "C:/model.gguf",
            "C:model.gguf",
            "/model.gguf",
            "\\\\server\\share",
            "../model.gguf",
            "models/../model.gguf",
            "models\\model.gguf",
            "models//model.gguf",
            "models/CON.txt",
            "models/model.gguf.",
        ] {
            assert!(
                validate_relative_windows_path(rejected).is_err(),
                "path should be rejected: {rejected}"
            );
        }
        assert!(validate_relative_windows_path("models/model.gguf").is_ok());
    }

    #[test]
    fn live_inventory_revalidates_exact_bytes_and_ignores_appdata_authority() {
        let workspace = TestWorkspace::new();
        let catalog = test_catalog();
        let runtime_path = install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
        let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        let service = service_for(&catalog, &workspace);

        let inventory = service.installed_artifacts();
        assert_eq!(inventory.artifacts.len(), 2);
        assert!(inventory
            .artifacts
            .iter()
            .all(|artifact| artifact.installation_status == InstallationStatus::Valid));
        let readiness = service.model_readiness("test-model").expect("readiness");
        assert_eq!(readiness.compatibility, CompatibilityStatus::Compatible);
        assert_eq!(readiness.readiness, ModelReadiness::Ready);
        assert!(readiness.launchable);

        fs::create_dir_all(&workspace.roots().state_root).expect("create state root");
        fs::write(
            workspace
                .roots()
                .state_root
                .join("installed-artifacts.v1.json"),
            br#"{"approved":true,"artifact_id":"unknown-runtime","catalog_digest":"stale"}"#,
        )
        .expect("write hostile inventory");
        fs::write(
            workspace.roots().model_root.join("unapproved.gguf"),
            b"GGUFunapproved",
        )
        .expect("write unapproved model");
        assert!(service
            .artifact_validation_status("unknown-runtime")
            .is_err());
        assert_eq!(service.installed_artifacts().artifacts.len(), 2);

        fs::write(&model_path, b"GGUFtest-mOdel").expect("tamper model");
        let model_status = service
            .artifact_validation_status("test-model")
            .expect("known model status");
        assert_eq!(
            model_status.installation_status,
            InstallationStatus::HashMismatch
        );
        assert!(
            !service
                .model_readiness("test-model")
                .expect("readiness")
                .launchable
        );

        fs::write(&model_path, b"short").expect("truncate model");
        assert_eq!(
            service
                .artifact_validation_status("test-model")
                .expect("known model status")
                .installation_status,
            InstallationStatus::BytesMismatch
        );

        fs::write(&runtime_path, b"test-runtimE").expect("tamper runtime");
        assert_eq!(
            service
                .artifact_validation_status("test-runtime")
                .expect("known runtime status")
                .installation_status,
            InstallationStatus::HashMismatch
        );
    }

    #[test]
    fn runtime_package_rejects_unlisted_files_and_model_rejects_bad_magic() {
        let workspace = TestWorkspace::new();
        let catalog = test_catalog();
        install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
        let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        let service = service_for(&catalog, &workspace);

        let package = workspace
            .roots()
            .runtime_root
            .join(&catalog.runtimes[0].managed_relative_path);
        fs::write(package.join("unlisted.txt"), b"not approved").expect("write extra file");
        assert_eq!(
            service
                .artifact_validation_status("test-runtime")
                .expect("runtime status")
                .installation_status,
            InstallationStatus::UnexpectedFile
        );

        fs::write(&model_path, b"NOPEtest-model").expect("replace magic");
        assert_eq!(
            service
                .artifact_validation_status("test-model")
                .expect("model status")
                .installation_status,
            InstallationStatus::InvalidFormat
        );
    }

    #[test]
    fn readiness_distinguishes_missing_invalid_and_incompatible_runtime() {
        let workspace = TestWorkspace::new();
        let mut catalog = test_catalog();
        catalog.runtimes = vec![
            test_runtime("aaa-compatible-runtime", "aaa-compatible-runtime"),
            test_runtime("zzz-incompatible-runtime", "zzz-incompatible-runtime"),
        ];
        catalog.models[0].compatible_runtime_ids = vec!["aaa-compatible-runtime".into()];
        install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        install_runtime(&workspace, &catalog.runtimes[1], TEST_RUNTIME_BYTES);
        let service = service_for(&catalog, &workspace);

        let readiness = service.model_readiness("test-model").expect("readiness");
        assert_eq!(
            readiness.compatibility,
            CompatibilityStatus::IncompatibleRuntimeInstalled
        );
        assert_eq!(readiness.readiness, ModelReadiness::Incompatible);
        assert!(!readiness.launchable);

        install_runtime(&workspace, &catalog.runtimes[0], b"test-runtimE");
        let readiness = service.model_readiness("test-model").expect("readiness");
        assert_eq!(readiness.readiness, ModelReadiness::RuntimeInvalid);
        assert!(!readiness.launchable);
    }

    #[cfg(windows)]
    #[test]
    fn resolved_launch_holds_model_and_runtime_identity_guards() {
        let workspace = TestWorkspace::new();
        let catalog = test_catalog();
        let runtime_path = install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
        let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        let service = service_for(&catalog, &workspace);
        let launch = service
            .resolve_launch("test-model")
            .expect("resolve launch");

        assert!(OpenOptions::new().write(true).open(&model_path).is_err());
        assert!(OpenOptions::new().write(true).open(&runtime_path).is_err());
        drop(launch);
        assert!(OpenOptions::new().write(true).open(&model_path).is_ok());
        assert!(OpenOptions::new().write(true).open(&runtime_path).is_ok());
    }

    #[cfg(windows)]
    #[test]
    fn app_data_ancestor_reparse_point_is_rejected_when_supported() {
        use std::os::windows::fs::symlink_dir;

        let workspace = TestWorkspace::new();
        let redirected = workspace.root.join("redirected-localcomet");
        fs::create_dir_all(redirected.join("runtimes")).expect("create redirected runtime root");
        fs::create_dir_all(redirected.join("models")).expect("create redirected model root");
        let localcomet_link = workspace.root.join("LocalComet");
        if symlink_dir(&redirected, &localcomet_link).is_err() {
            eprintln!("symbolic-link creation unavailable; lexical containment remains covered");
            return;
        }

        let catalog = test_catalog();
        let roots = ManagedArtifactRoots {
            app_data_root: workspace.root.clone(),
            runtime_root: localcomet_link.join("runtimes"),
            model_root: localcomet_link.join("models"),
            state_root: localcomet_link.join("state"),
        };
        let service = ArtifactTrustService::from_catalog_bytes(&canonical_bytes(&catalog), roots)
            .expect("valid catalog");
        let package = redirected
            .join("runtimes")
            .join(&catalog.runtimes[0].managed_relative_path);
        fs::create_dir_all(&package).expect("create redirected package");
        fs::write(package.join("llama-server.exe"), TEST_RUNTIME_BYTES)
            .expect("write redirected runtime");

        assert_eq!(
            service
                .artifact_validation_status("test-runtime")
                .expect("known runtime")
                .installation_status,
            InstallationStatus::InvalidPath
        );
        fs::remove_dir(&localcomet_link).expect("remove test link");
    }
}
