use crate::artifact_validation_cache::{ArtifactValidationCache, ValidationSource};
use crate::control_plane::BridgeError;
use reqwest::Url;
use serde::de::{MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::borrow::Cow;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, RwLock};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::State;

#[cfg(windows)]
use std::os::windows::{
    ffi::OsStrExt,
    fs::{MetadataExt, OpenOptionsExt},
    io::FromRawHandle,
};

#[cfg(windows)]
use windows_sys::Win32::Foundation::{GENERIC_READ, INVALID_HANDLE_VALUE};

#[cfg(windows)]
use windows_sys::Win32::Storage::FileSystem::{
    CreateFileW, GetDiskFreeSpaceExW, MoveFileExW, FILE_FLAG_BACKUP_SEMANTICS,
    FILE_FLAG_OPEN_REPARSE_POINT, FILE_SHARE_READ, FILE_SHARE_WRITE, MOVEFILE_REPLACE_EXISTING,
    MOVEFILE_WRITE_THROUGH, OPEN_EXISTING,
};

const CATALOG_BYTES: &[u8] = include_bytes!("../resources/localcomet/approved-artifacts.v1.json");
const EMBEDDED_CATALOG_SHA256: &str =
    "54e241d113d3fd2c57f1c0be74a8b9bcf56dd7c0a29d86c04ad641d719b3e081";
const CATALOG_ID: &str = "localcomet-approved-artifacts";
const SCHEMA_VERSION: u32 = 1;
const MAX_ARTIFACTS: usize = 32;
const MAX_REQUIRED_FILES: usize = 128;
const MAX_RUNTIME_ARCHIVE_MEMBERS: usize = 128;
const MAX_RUNTIME_ARCHIVE_BYTES: u64 = 4 * 1024 * 1024 * 1024;
pub(crate) const MAX_MODEL_BYTES: u64 = 128 * 1024 * 1024 * 1024;
pub(crate) const MAX_CUSTOM_MODELS: usize = 32;
const MAX_CUSTOM_MANIFEST_BYTES: u64 = 1024 * 1024;
const CUSTOM_MANIFEST_FILENAME: &str = "custom-models.v1.json";
const CUSTOM_MODEL_RUNTIME_ID: &str = "llama-cpp-windows-x86-64-cpu-bootstrap";
const VULKAN_MODEL_RUNTIME_ID: &str = "llama-cpp-windows-x86-64-vulkan-bootstrap";
const CUSTOM_MODEL_ID_PREFIX: &str = "custom-hf-";
const MODEL_ROOT_SENTINEL: &str = "<MANAGED_MODEL_ROOT>";
static CUSTOM_MANIFEST_TEMP_SEQUENCE: AtomicU64 = AtomicU64::new(0);
const INTERNAL_BOOTSTRAP_PURPOSE: &str = "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION";
const LLAMA_CPP_LICENSE_SOURCE_PATH: &str = "third_party/llama.cpp/LICENSE-MIT.txt";
const LLAMA_CPP_LICENSE_BYTES: &[u8] =
    include_bytes!("../../../../third_party/llama.cpp/LICENSE-MIT.txt");

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CatalogStatus {
    ApprovedInternalBootstrap,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionArtifactKind {
    Runtime,
    Model,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionSourceType {
    ApprovedHttps,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedArtifactAcquisition {
    pub artifact_id: String,
    pub artifact_kind: AcquisitionArtifactKind,
    pub source_type: AcquisitionSourceType,
    pub primary_url: String,
    pub allowed_redirect_hosts: Vec<String>,
    pub expected_filename: String,
    pub expected_bytes: u64,
    pub expected_sha256: String,
    pub content_type: Option<String>,
    pub managed_relative_destination: String,
    pub public_distribution: bool,
    pub installer_bundled: bool,
    pub automatic_download: bool,
    pub user_confirmation_required: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeFile {
    pub relative_path: String,
    pub bytes: u64,
    pub sha256: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeArchiveMemberDisposition {
    Install,
    RecognizedNotInstalled,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeArchiveMember {
    pub relative_path: String,
    pub disposition: RuntimeArchiveMemberDisposition,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeLicenseAsset {
    pub source_relative_path: String,
    pub destination_relative_path: String,
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
    pub acquisition: ApprovedArtifactAcquisition,
    pub archive_format: String,
    pub managed_relative_path: String,
    pub executable_relative_path: String,
    pub archive_members: Vec<ApprovedRuntimeArchiveMember>,
    pub required_files: Vec<ApprovedRuntimeFile>,
    pub license_asset: ApprovedRuntimeLicenseAsset,
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
    pub acquisition: ApprovedArtifactAcquisition,
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

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct CustomModelManifest {
    pub schema_version: u32,
    pub models: Vec<CustomModelArtifact>,
}

impl Default for CustomModelManifest {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION,
            models: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct CustomModelArtifact {
    pub model_id: String,
    pub display_name: String,
    pub source_url: String,
    pub source_repository: String,
    pub source_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub compatible_runtime_ids: Vec<String>,
    pub managed_relative_path: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct ValidatedCustomModelSource {
    pub model_id: String,
    pub display_name: String,
    pub source_url: String,
    pub source_repository: String,
    pub source_revision: String,
    pub asset_filename: String,
    pub compatible_runtime_ids: Vec<String>,
    pub managed_relative_path: String,
}

impl ValidatedCustomModelSource {
    pub(crate) fn into_artifact(
        self,
        asset_bytes: u64,
        asset_sha256: String,
    ) -> CustomModelArtifact {
        CustomModelArtifact {
            model_id: self.model_id,
            display_name: self.display_name,
            source_url: self.source_url,
            source_repository: self.source_repository,
            source_revision: self.source_revision,
            asset_filename: self.asset_filename,
            asset_bytes,
            asset_sha256,
            compatible_runtime_ids: self.compatible_runtime_ids,
            managed_relative_path: self.managed_relative_path,
        }
    }
}

#[derive(Clone, Debug)]
pub(crate) struct ManagedArtifactRoots {
    pub app_data_root: PathBuf,
    pub runtime_root: PathBuf,
    pub model_root: PathBuf,
    pub state_root: PathBuf,
}

impl ManagedArtifactRoots {
    pub(crate) fn from_application_data_root(application_data_root: &Path) -> Self {
        Self {
            app_data_root: application_data_root.to_path_buf(),
            runtime_root: application_data_root.join("runtimes").join("llama.cpp"),
            model_root: application_data_root.join("models"),
            state_root: application_data_root.join("runtime-state"),
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

    pub(crate) fn code(&self) -> &'static str {
        self.code
    }
}

pub(crate) fn source_controlled_runtime_license_bytes(
    asset: &ApprovedRuntimeLicenseAsset,
) -> Result<&'static [u8], ArtifactTrustError> {
    if asset.source_relative_path != LLAMA_CPP_LICENSE_SOURCE_PATH
        || asset.bytes != LLAMA_CPP_LICENSE_BYTES.len() as u64
        || sha256_bytes(LLAMA_CPP_LICENSE_BYTES) != asset.sha256
    {
        return Err(ArtifactTrustError::new(
            "invalid_license_asset",
            "runtime license asset identity rejected",
        ));
    }
    Ok(LLAMA_CPP_LICENSE_BYTES)
}

impl From<ArtifactTrustError> for BridgeError {
    fn from(value: ArtifactTrustError) -> Self {
        BridgeError::new(value.code, &value.message)
    }
}
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactKind {
    Runtime,
    Model,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelTrustKind {
    ApprovedCatalog,
    UserSupplied,
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
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CustomModelSummary {
    pub model_id: String,
    pub display_name: String,
    pub format: String,
    pub source_url: String,
    pub source_repository: String,
    pub source_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub license_id: Option<String>,
    pub compatible_runtime_ids: Vec<String>,
    pub trust_kind: ModelTrustKind,
}

impl From<&CustomModelArtifact> for CustomModelSummary {
    fn from(model: &CustomModelArtifact) -> Self {
        Self {
            model_id: model.model_id.clone(),
            display_name: model.display_name.clone(),
            format: "GGUF".into(),
            source_url: model.source_url.clone(),
            source_repository: model.source_repository.clone(),
            source_revision: model.source_revision.clone(),
            asset_filename: model.asset_filename.clone(),
            asset_bytes: model.asset_bytes,
            asset_sha256: model.asset_sha256.clone(),
            license_id: None,
            compatible_runtime_ids: model.compatible_runtime_ids.clone(),
            trust_kind: ModelTrustKind::UserSupplied,
        }
    }
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
    pub custom_models: Vec<CustomModelSummary>,
    pub maximum_custom_models: usize,
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
pub struct CustomArtifactValidationSummary {
    pub artifact_id: String,
    pub kind: ArtifactKind,
    pub trust_kind: ModelTrustKind,
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
    pub custom_artifacts: Vec<CustomArtifactValidationSummary>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedArtifactTrustBundle {
    pub runtime_catalog: ManagedRuntimeCatalog,
    pub model_catalog: ManagedModelCatalog,
    pub installed_artifacts: ManagedInstalledArtifacts,
}

#[derive(Clone, Debug, Serialize)]
pub struct ModelStorageInfo {
    pub models_path: String,
    pub runtimes_path: String,
    pub free_bytes: Option<u64>,
    pub models_bytes: u64,
    pub installed_models: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct ModelReadinessSummary {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub model_id: String,
    pub model_trust_kind: ModelTrustKind,
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
struct SourcedValidationOutcome {
    outcome: ValidationOutcome,
    source: ValidationSource,
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
    pub mmproj_path: Option<PathBuf>,
    #[allow(dead_code)]
    pub mmproj_handle: Option<File>,
    pub runtime_handles: Vec<File>,
    pub directory_handles: Vec<File>,
    pub artifact_validation_source: ValidationSource,
    /// Every engine this model declares as compatible. Used to name a concrete
    /// CPU engine when an accelerated launch finds no device, instead of
    /// emitting a generic "select the CPU engine" dead-end.
    pub compatible_runtime_ids: Vec<String>,
}

/// A validated runtime binary location for capability probing. Carries no
/// model and no launch handles: probing grants no authority beyond running
/// the runtime's own device-list flag.
pub(crate) struct RuntimeProbeTarget {
    pub runtime_id: String,
    pub release_tag: String,
    pub package_dir: PathBuf,
    pub executable: PathBuf,
}

#[derive(Clone, Debug)]
pub(crate) enum ApprovedDownloadArtifact {
    Runtime(ApprovedRuntimeArtifact),
    Model(ApprovedModelArtifact),
}

#[derive(Clone, Debug)]
enum ManagedModelArtifact {
    Approved(Box<ApprovedModelArtifact>),
    Custom(Box<CustomModelArtifact>),
}

impl ManagedModelArtifact {
    fn model_id(&self) -> &str {
        match self {
            Self::Approved(model) => &model.model_id,
            Self::Custom(model) => &model.model_id,
        }
    }

    fn display_name(&self) -> &str {
        match self {
            Self::Approved(model) => &model.display_name,
            Self::Custom(model) => &model.display_name,
        }
    }

    fn compatible_runtime_ids(&self) -> &[String] {
        match self {
            Self::Approved(model) => &model.compatible_runtime_ids,
            Self::Custom(model) => &model.compatible_runtime_ids,
        }
    }

    #[allow(dead_code)]
    fn asset_bytes(&self) -> u64 {
        match self {
            Self::Approved(model) => model.asset_bytes,
            Self::Custom(model) => model.asset_bytes,
        }
    }

    fn managed_relative_path(&self) -> &str {
        match self {
            Self::Approved(model) => &model.managed_relative_path,
            Self::Custom(model) => &model.managed_relative_path,
        }
    }

    fn trust_kind(&self) -> ModelTrustKind {
        match self {
            Self::Approved(_) => ModelTrustKind::ApprovedCatalog,
            Self::Custom(_) => ModelTrustKind::UserSupplied,
        }
    }

    fn custom_sha256(&self) -> Option<&str> {
        match self {
            Self::Approved(_) => None,
            Self::Custom(model) => Some(&model.asset_sha256),
        }
    }
}

pub struct ArtifactTrustService {
    catalog: ApprovedArtifactCatalog,
    custom_models: RwLock<CustomModelManifest>,
    catalog_digest: String,
    roots: ManagedArtifactRoots,
    validation_cache: ArtifactValidationCache,
}

impl ArtifactTrustService {
    pub fn production(application_data_root: &Path) -> Result<Self, ArtifactTrustError> {
        let roots = ManagedArtifactRoots::from_application_data_root(application_data_root);
        ensure_managed_directories(&roots)?;
        let catalog_bytes = canonical_embedded_catalog_bytes()?;
        Self::from_catalog_bytes(catalog_bytes.as_ref(), roots)
    }

    pub(crate) fn from_catalog_bytes(
        bytes: &[u8],
        roots: ManagedArtifactRoots,
    ) -> Result<Self, ArtifactTrustError> {
        let catalog = parse_catalog(bytes)?;
        validate_catalog(&catalog)?;
        validate_canonical_catalog_bytes(bytes, &catalog)?;
        let catalog_digest = sha256_bytes(bytes);
        let validation_cache = ArtifactValidationCache::new(&roots.app_data_root, &catalog_digest);
        let custom_models = load_custom_manifest(&roots, &catalog).unwrap_or_default();

        Ok(Self {
            catalog,
            custom_models: RwLock::new(custom_models),
            catalog_digest,
            roots,
            validation_cache,
        })
    }

    pub(crate) fn roots(&self) -> &ManagedArtifactRoots {
        &self.roots
    }

    pub(crate) fn custom_models_snapshot(&self) -> Vec<CustomModelArtifact> {
        self.custom_models
            .read()
            .map(|manifest| manifest.models.clone())
            .unwrap_or_default()
    }

    pub(crate) fn custom_model(
        &self,
        model_id: &str,
    ) -> Result<Option<CustomModelArtifact>, ArtifactTrustError> {
        validate_artifact_id(model_id)?;
        let manifest = self.custom_models.read().map_err(|_| {
            ArtifactTrustError::new(
                "custom_manifest_unavailable",
                "custom model state unavailable",
            )
        })?;
        Ok(manifest
            .models
            .iter()
            .find(|model| model.model_id == model_id)
            .cloned())
    }

    pub(crate) fn ensure_custom_model_capacity(
        &self,
        model_id: &str,
    ) -> Result<(), ArtifactTrustError> {
        let manifest = self.custom_models.read().map_err(|_| {
            ArtifactTrustError::new(
                "custom_manifest_unavailable",
                "custom model state unavailable",
            )
        })?;
        if manifest
            .models
            .iter()
            .any(|model| model.model_id == model_id)
        {
            return Ok(());
        }
        if manifest.models.len() >= MAX_CUSTOM_MODELS {
            return Err(ArtifactTrustError::new(
                "custom_model_limit",
                "custom model limit reached",
            ));
        }
        Ok(())
    }

    #[cfg(test)]
    pub(crate) fn register_custom_model(
        &self,
        model: CustomModelArtifact,
    ) -> Result<(), ArtifactTrustError> {
        self.register_custom_model_with_validation(model, true)
    }

    pub(crate) fn register_custom_model_after_validation(
        &self,
        model: CustomModelArtifact,
    ) -> Result<(), ArtifactTrustError> {
        // The acquisition path forces a post-install hash before durable registration.
        self.register_custom_model_with_validation(model, false)
    }

    fn register_custom_model_with_validation(
        &self,
        model: CustomModelArtifact,
        force_full: bool,
    ) -> Result<(), ArtifactTrustError> {
        if self
            .validate_custom_model_artifact(&model, force_full)
            .installation_status
            != InstallationStatus::Valid
        {
            return Err(ArtifactTrustError::new(
                "custom_model_not_valid",
                "custom model must pass full validation before registration",
            ));
        }
        let mut manifest = self.custom_models.write().map_err(|_| {
            ArtifactTrustError::new(
                "custom_manifest_unavailable",
                "custom model state unavailable",
            )
        })?;
        if manifest
            .models
            .iter()
            .any(|existing| existing.model_id == model.model_id)
        {
            return Err(ArtifactTrustError::new(
                "custom_model_conflict",
                "custom model is already registered",
            ));
        }
        let mut candidate = manifest.clone();
        candidate.models.push(model);
        candidate
            .models
            .sort_by(|left, right| left.model_id.cmp(&right.model_id));
        validate_custom_manifest(&candidate, &self.catalog)?;
        persist_custom_manifest(&self.roots, &candidate)?;
        *manifest = candidate;
        Ok(())
    }

    pub(crate) fn unregister_custom_model(&self, model_id: &str) -> Result<(), ArtifactTrustError> {
        validate_artifact_id(model_id)?;
        let mut manifest = self.custom_models.write().map_err(|_| {
            ArtifactTrustError::new(
                "custom_manifest_unavailable",
                "custom model state unavailable",
            )
        })?;
        if !manifest
            .models
            .iter()
            .any(|model| model.model_id == model_id)
        {
            return Err(ArtifactTrustError::new(
                "unknown_artifact",
                "unknown custom model id",
            ));
        }
        let mut candidate = manifest.clone();
        candidate.models.retain(|model| model.model_id != model_id);
        validate_custom_manifest(&candidate, &self.catalog)?;
        persist_custom_manifest(&self.roots, &candidate)?;
        *manifest = candidate;
        Ok(())
    }

    pub(crate) fn invalidate_validation_cache_for_artifact(&self, artifact_id: &str) {
        if let Some(model) = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == artifact_id)
        {
            if let Ok(path) =
                resolve_contained(&self.roots.model_root, &model.managed_relative_path)
            {
                self.validation_cache.invalidate_path(&path);
            }
            return;
        }
        if let Ok(Some(model)) = self.custom_model(artifact_id) {
            if let Ok(path) =
                resolve_contained(&self.roots.model_root, &model.managed_relative_path)
            {
                self.validation_cache.invalidate_path(&path);
            }
            return;
        }
        if let Some(runtime) = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == artifact_id)
        {
            if let Ok(package) =
                resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path)
            {
                if let Some(asset) = runtime.required_files.iter().max_by_key(|file| file.bytes) {
                    if let Ok(path) = resolve_contained(&package, &asset.relative_path) {
                        self.validation_cache.invalidate_path(&path);
                    }
                }
            }
        }
    }

    pub(crate) fn guard_runtime_state_root(&self) -> Result<Vec<File>, ArtifactTrustError> {
        open_directory_guard_chain(&self.roots.app_data_root, &self.roots.state_root, true)
    }

    pub(crate) fn approved_download_artifact(
        &self,
        artifact_id: &str,
    ) -> Result<ApprovedDownloadArtifact, ArtifactTrustError> {
        validate_artifact_id(artifact_id)?;
        if let Some(runtime) = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == artifact_id)
        {
            return Ok(ApprovedDownloadArtifact::Runtime(runtime.clone()));
        }
        if let Some(model) = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == artifact_id)
        {
            return Ok(ApprovedDownloadArtifact::Model(model.clone()));
        }
        Err(ArtifactTrustError::new(
            "unknown_artifact",
            "unknown approved artifact id",
        ))
    }

    pub(crate) fn acquisition_root(&self) -> Result<PathBuf, ArtifactTrustError> {
        let root = resolve_contained(&self.roots.app_data_root, "acquisition")?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, &root, true)?;
        Ok(root)
    }

    pub(crate) fn acquisition_event_log_path(&self) -> Result<PathBuf, ArtifactTrustError> {
        let path = resolve_contained(&self.roots.app_data_root, "logs/acquisition-events.jsonl")?;
        let parent = path
            .parent()
            .ok_or_else(|| ArtifactTrustError::new("invalid_path", "log parent unavailable"))?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, parent, true)?;
        Ok(path)
    }

    pub(crate) fn download_destination(
        &self,
        artifact: &ApprovedDownloadArtifact,
    ) -> Result<PathBuf, ArtifactTrustError> {
        let (root, relative) = match artifact {
            ApprovedDownloadArtifact::Runtime(runtime) => {
                (&self.roots.runtime_root, &runtime.managed_relative_path)
            }
            ApprovedDownloadArtifact::Model(model) => {
                (&self.roots.model_root, &model.managed_relative_path)
            }
        };
        let destination = resolve_contained(root, relative)?;
        let parent = destination
            .parent()
            .ok_or_else(|| ArtifactTrustError::new("invalid_path", "managed parent unavailable"))?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, parent, true)?;
        Ok(destination)
    }

    pub(crate) fn custom_download_destination(
        &self,
        source: &ValidatedCustomModelSource,
    ) -> Result<PathBuf, ArtifactTrustError> {
        let destination = resolve_contained(&self.roots.model_root, &source.managed_relative_path)?;
        let parent = destination.parent().ok_or_else(|| {
            ArtifactTrustError::new("invalid_path", "custom model parent unavailable")
        })?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, parent, true)?;
        Ok(destination)
    }

    pub(crate) fn custom_model_destination(
        &self,
        model: &CustomModelArtifact,
    ) -> Result<PathBuf, ArtifactTrustError> {
        resolve_contained(&self.roots.model_root, &model.managed_relative_path)
    }

    pub(crate) fn remove_custom_model_file_if_present(
        &self,
        model: &CustomModelArtifact,
    ) -> Result<bool, ArtifactTrustError> {
        let path = self.custom_model_destination(model)?;
        let metadata = match fs::symlink_metadata(&path) {
            Ok(metadata) => metadata,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
            Err(_) => {
                return Err(ArtifactTrustError::new(
                    "model_removal_failed",
                    "custom model metadata unavailable",
                ))
            }
        };
        let parent = path.parent().ok_or_else(|| {
            ArtifactTrustError::new("invalid_path", "custom model parent unavailable")
        })?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, parent, false)?;
        if !metadata.is_file()
            || ensure_existing_safe_path(
                &self.roots.app_data_root,
                &self.roots.model_root,
                &path,
                false,
            )
            .is_err()
        {
            return Err(ArtifactTrustError::new(
                "invalid_path",
                "custom model removal path rejected",
            ));
        }
        fs::remove_file(&path).map_err(|_| {
            ArtifactTrustError::new("model_removal_failed", "custom model removal failed")
        })?;
        Ok(true)
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
                })
                .collect(),
        }
    }

    pub fn model_catalog(&self) -> ManagedModelCatalog {
        let custom_models = self.custom_models_snapshot();
        self.model_catalog_from_custom(&custom_models)
    }

    fn model_catalog_from_custom(
        &self,
        custom_models: &[CustomModelArtifact],
    ) -> ManagedModelCatalog {
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
                })
                .collect(),
            maximum_models: MAX_ARTIFACTS,
            custom_models: custom_models.iter().map(CustomModelSummary::from).collect(),
            maximum_custom_models: MAX_CUSTOM_MODELS,
        }
    }

    pub fn installed_artifacts(&self) -> ManagedInstalledArtifacts {
        let custom_models = self.custom_models_snapshot();
        self.installed_artifacts_from_custom(&custom_models)
    }

    fn installed_artifacts_from_custom(
        &self,
        custom_models: &[CustomModelArtifact],
    ) -> ManagedInstalledArtifacts {
        let mut artifacts = Vec::new();
        for runtime in &self.catalog.runtimes {
            artifacts.push(self.runtime_validation_summary(runtime));
        }
        for model in &self.catalog.models {
            artifacts.push(self.model_validation_summary(model));
        }
        let custom_artifacts = custom_models
            .iter()
            .map(|model| self.custom_model_validation_summary(model))
            .collect();
        ManagedInstalledArtifacts {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            artifacts,
            custom_artifacts,
        }
    }

    pub fn artifact_trust_bundle(&self) -> ManagedArtifactTrustBundle {
        let custom_models = self.custom_models_snapshot();
        ManagedArtifactTrustBundle {
            runtime_catalog: self.runtime_catalog(),
            model_catalog: self.model_catalog_from_custom(&custom_models),
            installed_artifacts: self.installed_artifacts_from_custom(&custom_models),
        }
    }

    pub fn model_storage_info(&self) -> ModelStorageInfo {
        let custom_models = self.custom_models_snapshot();
        let installed = self.installed_artifacts_from_custom(&custom_models);
        let installed_models = installed
            .artifacts
            .iter()
            .filter(|artifact| {
                artifact.kind == ArtifactKind::Model
                    && artifact.installation_status == InstallationStatus::Valid
            })
            .count()
            + installed
                .custom_artifacts
                .iter()
                .filter(|artifact| artifact.installation_status == InstallationStatus::Valid)
                .count();
        ModelStorageInfo {
            models_path: self.roots.model_root.to_string_lossy().into_owned(),
            runtimes_path: self.roots.runtime_root.to_string_lossy().into_owned(),
            free_bytes: available_space(&self.roots.model_root),
            models_bytes: directory_file_bytes(&self.roots.model_root),
            installed_models,
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

    fn managed_model_artifact(
        &self,
        model_id: &str,
    ) -> Result<ManagedModelArtifact, ArtifactTrustError> {
        validate_artifact_id(model_id)?;
        if let Some(model) = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == model_id)
        {
            return Ok(ManagedModelArtifact::Approved(Box::new(model.clone())));
        }
        self.custom_model(model_id)?
            .map(|model| ManagedModelArtifact::Custom(Box::new(model)))
            .ok_or_else(|| ArtifactTrustError::new("unknown_artifact", "unknown model id"))
    }

    pub(crate) fn runtime_start_approval_input(
        &self,
        model_id: &str,
        custom_sha256: Option<&str>,
        runtime_id: Option<&str>,
    ) -> Result<Value, ArtifactTrustError> {
        let model = self.managed_model_artifact(model_id)?;
        let runtime_id = match runtime_id {
            Some("") => None,
            Some(candidate) => {
                if !model
                    .compatible_runtime_ids()
                    .iter()
                    .any(|id| id == candidate)
                {
                    return Err(ArtifactTrustError::new(
                        "runtime_id_not_compatible",
                        "requested runtime is not compatible with this model",
                    ));
                }
                Some(candidate.to_owned())
            }
            None => None,
        };
        match model {
            ManagedModelArtifact::Approved(_) if custom_sha256.is_some() => {
                Err(ArtifactTrustError::new(
                    "custom_sha256_rejected",
                    "approved model does not accept a custom digest",
                ))
            }
            ManagedModelArtifact::Approved(_) => match &runtime_id {
                Some(runtime_id) => Ok(serde_json::json!({
                    "model_id": model_id,
                    "runtime_id": runtime_id,
                })),
                None => Ok(serde_json::json!({ "model_id": model_id })),
            },
            ManagedModelArtifact::Custom(model) => {
                let supplied = custom_sha256.ok_or_else(|| {
                    ArtifactTrustError::new(
                        "custom_sha256_required",
                        "custom model start requires its local digest",
                    )
                })?;
                validate_sha256(supplied)?;
                if supplied != model.asset_sha256 {
                    return Err(ArtifactTrustError::new(
                        "custom_sha256_mismatch",
                        "custom model digest does not match durable state",
                    ));
                }
                match &runtime_id {
                    Some(runtime_id) => Ok(serde_json::json!({
                        "model_id": model_id,
                        "custom_sha256": supplied,
                        "runtime_id": runtime_id,
                    })),
                    None => Ok(serde_json::json!({
                        "model_id": model_id,
                        "custom_sha256": supplied,
                    })),
                }
            }
        }
    }

    pub fn model_readiness(
        &self,
        model_id: &str,
    ) -> Result<ModelReadinessSummary, ArtifactTrustError> {
        let model = self.managed_model_artifact(model_id)?;
        self.model_readiness_for(&model).map(|(summary, _)| summary)
    }

    fn model_readiness_for(
        &self,
        model: &ManagedModelArtifact,
    ) -> Result<(ModelReadinessSummary, ValidationSource), ArtifactTrustError> {
        let model_validation = self.validate_managed_model(model, force_full_validation());
        let mut validation_source = model_validation.source;
        let model_outcome = model_validation.outcome;
        let mut selected_runtime_id = None;
        let mut selected_runtime_status = None;
        let mut saw_invalid_runtime = false;
        let mut runtime_candidates: Vec<&str> = model
            .compatible_runtime_ids()
            .iter()
            .map(String::as_str)
            .collect();
        runtime_candidates.sort_by_key(|id| if *id == VULKAN_MODEL_RUNTIME_ID { 0 } else { 1 });
        for runtime_id in runtime_candidates {
            let runtime = self
                .catalog
                .runtimes
                .iter()
                .find(|runtime| runtime.runtime_id == runtime_id)
                .ok_or_else(|| {
                    ArtifactTrustError::new("invalid_catalog", "unknown compatible runtime")
                })?;
            let validation = self.validate_runtime(runtime);
            validation_source = validation_source.combine(validation.source);
            let outcome = validation.outcome;
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
        if selected_runtime_id.is_none() {
            let mut preferred_runtime_id: Option<String> = None;
            if model
                .compatible_runtime_ids()
                .iter()
                .any(|id| id == VULKAN_MODEL_RUNTIME_ID)
            {
                preferred_runtime_id = Some(VULKAN_MODEL_RUNTIME_ID.to_string());
            } else if model
                .compatible_runtime_ids()
                .iter()
                .any(|id| id == CUSTOM_MODEL_RUNTIME_ID)
            {
                preferred_runtime_id = Some(CUSTOM_MODEL_RUNTIME_ID.to_string());
            }
            if let Some(pref) = preferred_runtime_id {
                selected_runtime_id = Some(pref);
                selected_runtime_status = Some(InstallationStatus::NotInstalled);
            }
        }

        let incompatible_runtime_installed = selected_runtime_id.is_none()
            && self.catalog.runtimes.iter().any(|runtime| {
                !model
                    .compatible_runtime_ids()
                    .iter()
                    .any(|runtime_id| runtime_id == &runtime.runtime_id)
                    && self.validate_runtime(runtime).outcome.status == InstallationStatus::Valid
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
        Ok((
            ModelReadinessSummary {
                schema_version: self.catalog.schema_version,
                catalog_id: self.catalog.catalog_id.clone(),
                catalog_version: self.catalog.catalog_version.clone(),
                catalog_digest: self.catalog_digest.clone(),
                model_id: model.model_id().to_string(),
                model_trust_kind: model.trust_kind(),
                model_status: model_outcome.status,
                compatible_runtime_ids: model.compatible_runtime_ids().to_vec(),
                selected_runtime_id,
                runtime_status: selected_runtime_status,
                compatibility,
                readiness,
                launchable,
            },
            validation_source,
        ))
    }

    #[cfg(test)]
    pub(crate) fn resolve_launch(
        &self,
        model_id: &str,
    ) -> Result<ValidatedRuntimeModel, ArtifactTrustError> {
        self.resolve_launch_inner(model_id, None, None, false)
    }

    pub(crate) fn resolve_launch_for_start(
        &self,
        model_id: &str,
        custom_sha256: Option<&str>,
        runtime_id: Option<&str>,
    ) -> Result<ValidatedRuntimeModel, ArtifactTrustError> {
        let model = self.managed_model_artifact(model_id)?;
        if matches!(model, ManagedModelArtifact::Approved(_)) && custom_sha256.is_none() {
            return self.resolve_launch_with_runtime(model_id, runtime_id);
        }
        self.resolve_launch_inner(model_id, custom_sha256, runtime_id, true)
    }

    fn resolve_launch_with_runtime(
        &self,
        model_id: &str,
        runtime_id: Option<&str>,
    ) -> Result<ValidatedRuntimeModel, ArtifactTrustError> {
        self.resolve_launch_inner(model_id, None, runtime_id, false)
    }

    /// Runtime-only probe target for capability reporting (P0-6). Validates the
    /// installed runtime package through the same cache-backed validator as the
    /// launch path, but binds no model. The caller never receives launch
    /// authority from this: it only learns where a validated runtime binary
    /// lives so it can probe device support.
    pub(crate) fn runtime_probe_target(
        &self,
        runtime_id: &str,
    ) -> Result<RuntimeProbeTarget, ArtifactTrustError> {
        let runtime = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == runtime_id)
            .ok_or_else(|| {
                ArtifactTrustError::new(
                    "invalid_runtime_id",
                    "runtime is not in the approved catalog",
                )
            })?;
        let validation = self.validate_runtime(runtime);
        if validation.outcome.status != InstallationStatus::Valid {
            return Err(ArtifactTrustError::new(
                "runtime_not_installed",
                "runtime is not installed or not valid",
            ));
        }
        let package_dir =
            resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path)?;
        let executable = resolve_contained(&package_dir, &runtime.executable_relative_path)?;
        Ok(RuntimeProbeTarget {
            runtime_id: runtime.runtime_id.clone(),
            release_tag: runtime.release_tag.clone(),
            package_dir,
            executable,
        })
    }

    /// Resolves the primary `.gguf` file of a managed model without taking
    /// launch guards. Capability reporting only: the launch path keeps its own
    /// guard-protected resolution and remains authoritative for starting.
    pub(crate) fn managed_model_file(&self, model_id: &str) -> Result<PathBuf, ArtifactTrustError> {
        let model = self.managed_model_artifact(model_id)?;
        if matches!(model, ManagedModelArtifact::Custom(_)) {
            let custom_dir = self
                .roots
                .model_root
                .join(format!("custom/{}", model.model_id()));
            if let Ok(entries) = std::fs::read_dir(&custom_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    let is_gguf = path
                        .extension()
                        .map(|ext| ext.to_string_lossy().to_lowercase() == "gguf")
                        .unwrap_or(false);
                    if path.is_file() && is_gguf {
                        return Ok(path);
                    }
                }
            }
            return resolve_contained(&self.roots.model_root, model.managed_relative_path());
        }
        resolve_contained(&self.roots.model_root, model.managed_relative_path())
    }

    fn resolve_launch_inner(
        &self,
        model_id: &str,
        custom_sha256: Option<&str>,
        runtime_id: Option<&str>,
        require_approval_binding: bool,
    ) -> Result<ValidatedRuntimeModel, ArtifactTrustError> {
        let model = self.managed_model_artifact(model_id)?;
        if require_approval_binding {
            match (model.custom_sha256(), custom_sha256) {
                (None, None) => {}
                (None, Some(_)) => {
                    return Err(ArtifactTrustError::new(
                        "custom_sha256_rejected",
                        "approved model does not accept a custom digest",
                    ))
                }
                (Some(_), None) => {
                    return Err(ArtifactTrustError::new(
                        "custom_sha256_required",
                        "custom model start requires its local digest",
                    ))
                }
                (Some(expected), Some(supplied)) if expected == supplied => {}
                (Some(_), Some(_)) => {
                    return Err(ArtifactTrustError::new(
                        "custom_sha256_mismatch",
                        "custom model digest changed after approval",
                    ))
                }
            }
        }
        let requested_runtime = match runtime_id {
            Some(candidate) => {
                if !model
                    .compatible_runtime_ids()
                    .iter()
                    .any(|id| id == candidate)
                {
                    return Err(ArtifactTrustError::new(
                        "artifact_not_ready",
                        "requested runtime is not compatible with this model",
                    ));
                }
                let requested = self
                    .catalog
                    .runtimes
                    .iter()
                    .find(|runtime| runtime.runtime_id == candidate)
                    .ok_or_else(|| {
                        ArtifactTrustError::new("invalid_catalog", "runtime unavailable")
                    })?;
                let model_validation = self.validate_managed_model(&model, force_full_validation());
                let validation = self.validate_runtime(requested);
                if model_validation.outcome.status != InstallationStatus::Valid {
                    return Err(ArtifactTrustError::new(
                        "artifact_not_ready",
                        "managed model is not valid; refusing launch",
                    ));
                }
                if validation.outcome.status != InstallationStatus::Valid {
                    return Err(ArtifactTrustError::new(
                        "artifact_not_ready",
                        "requested runtime is not valid; refusing launch",
                    ));
                }
                let validation_source = model_validation.source.combine(validation.source);
                (requested, validation_source)
            }
            None => {
                let (readiness, validation_source) = self.model_readiness_for(&model)?;
                if !readiness.launchable {
                    return Err(ArtifactTrustError::new(
                        "artifact_not_ready",
                        "managed runtime/model pair is not ready",
                    ));
                }
                let runtime_id = readiness.selected_runtime_id.ok_or_else(|| {
                    ArtifactTrustError::new("artifact_not_ready", "runtime unavailable")
                })?;
                let runtime = self
                    .catalog
                    .runtimes
                    .iter()
                    .find(|runtime| runtime.runtime_id == runtime_id)
                    .ok_or_else(|| {
                        ArtifactTrustError::new("invalid_catalog", "runtime unavailable")
                    })?;
                (runtime, validation_source)
            }
        };
        let (runtime, mut validation_source) = requested_runtime;
        let package_dir =
            resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path)?;
        let executable = resolve_contained(&package_dir, &runtime.executable_relative_path)?;
        let (model_path, mmproj_path) = if matches!(model, ManagedModelArtifact::Custom(_)) {
            let custom_dir = self
                .roots
                .model_root
                .join(format!("custom/{}", model.model_id()));
            let mut gguf_path = None;
            let mut mmproj_found = None;
            if let Ok(entries) = std::fs::read_dir(&custom_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_file() {
                        if let Some(ext) = path.extension() {
                            let ext_str = ext.to_string_lossy().to_lowercase();
                            if ext_str == "gguf" || ext_str == "mmproj" {
                                let filename = path
                                    .file_name()
                                    .unwrap_or_default()
                                    .to_string_lossy()
                                    .to_lowercase();
                                if filename.contains("mmproj") || ext_str == "mmproj" {
                                    mmproj_found = Some(path.clone());
                                } else if ext_str == "gguf" {
                                    gguf_path = Some(path.clone());
                                }
                            }
                        }
                    }
                }
            }
            let gguf_path = gguf_path.unwrap_or_else(|| {
                resolve_contained(&self.roots.model_root, model.managed_relative_path())
                    .unwrap_or_default()
            });
            if gguf_path.as_os_str().is_empty() {
                return Err(ArtifactTrustError::new(
                    "missing_custom_model",
                    "no .gguf file found in custom model directory",
                ));
            }
            (gguf_path, mmproj_found)
        } else {
            (
                resolve_contained(&self.roots.model_root, model.managed_relative_path())?,
                None,
            )
        };

        let is_vision_model = model.display_name().contains("-VL-")
            || model.model_id().contains("-VL-")
            || model.model_id().contains("-vl-");
        if is_vision_model && mmproj_path.is_none() {
            return Err(ArtifactTrustError::new(
                "missing_mmproj",
                "vision model requires mmproj file",
            ));
        }

        let model_parent = model_path
            .parent()
            .ok_or_else(|| ArtifactTrustError::new("invalid_path", "model parent unavailable"))?;
        let mut directory_handles =
            open_directory_guard_chain(&self.roots.app_data_root, &package_dir, false)?;
        directory_handles.extend(open_directory_guard_chain(
            &self.roots.app_data_root,
            model_parent,
            false,
        )?);
        for required in &runtime.required_files {
            let path = resolve_contained(&package_dir, &required.relative_path)?;
            let parent = path.parent().ok_or_else(|| {
                ArtifactTrustError::new("invalid_path", "runtime file parent unavailable")
            })?;
            directory_handles.extend(open_directory_guard_chain(
                &self.roots.app_data_root,
                parent,
                false,
            )?);
        }
        let model_handle = open_model_guard(&model_path)?;
        let mmproj_handle = match &mmproj_path {
            Some(path) => Some(open_model_guard(path)?),
            None => None,
        };
        let mut runtime_handles = Vec::with_capacity(runtime.required_files.len());
        for required in &runtime.required_files {
            let path = resolve_contained(&package_dir, &required.relative_path)?;
            runtime_handles.push(open_runtime_guard(&path)?);
        }
        // The recheck runs while exclusive model/runtime guards are already
        // held, so the file identity cannot change between the validations
        // earlier in this same launch and this recheck. Re-hashing the whole
        // GGUF here forced a multi-second (multi-GB) stall on every start;
        // the cache proves the same bytes that were fully hashed above.
        let model_recheck = self.validate_managed_model(&model, false);
        validation_source = validation_source.combine(model_recheck.source);
        if model_recheck.outcome.status != InstallationStatus::Valid {
            return Err(ArtifactTrustError::new(
                "artifact_changed",
                "model identity changed before launch",
            ));
        }
        let runtime_recheck = self.validate_runtime(runtime);
        validation_source = validation_source.combine(runtime_recheck.source);
        if runtime_recheck.outcome.status != InstallationStatus::Valid {
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
            model_id: model.model_id().to_string(),
            model_display_name: model.display_name().to_string(),
            model_path,
            model_handle,
            mmproj_path,
            mmproj_handle,
            runtime_handles,
            directory_handles,
            artifact_validation_source: validation_source,
            compatible_runtime_ids: model.compatible_runtime_ids().to_vec(),
        })
    }

    pub(crate) fn has_valid_runtime(&self) -> bool {
        self.catalog.runtimes.iter().any(|runtime| {
            self.validate_runtime(runtime).outcome.status == InstallationStatus::Valid
        })
    }

    fn runtime_validation_summary(
        &self,
        runtime: &ApprovedRuntimeArtifact,
    ) -> ArtifactValidationSummary {
        let outcome = self.validate_runtime(runtime).outcome;
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
        let outcome = self.validate_model(model).outcome;
        self.validation_summary(
            &model.model_id,
            ArtifactKind::Model,
            model.status.clone(),
            model.asset_bytes,
            &model.asset_sha256,
            outcome,
        )
    }

    fn custom_model_validation_summary(
        &self,
        model: &CustomModelArtifact,
    ) -> CustomArtifactValidationSummary {
        let outcome = self
            .validate_custom_model(model, force_full_validation())
            .outcome;
        CustomArtifactValidationSummary {
            artifact_id: model.model_id.clone(),
            kind: ArtifactKind::Model,
            trust_kind: ModelTrustKind::UserSupplied,
            installation_status: outcome.status,
            expected_bytes: model.asset_bytes,
            expected_sha256: model.asset_sha256.clone(),
            observed_bytes: outcome.observed_bytes,
            observed_sha256: outcome.observed_sha256,
            validation_code: outcome.code.into(),
            verified_unix_ms: now_unix_ms(),
        }
    }

    pub(crate) fn validate_custom_model_artifact(
        &self,
        model: &CustomModelArtifact,
        force_full: bool,
    ) -> CustomArtifactValidationSummary {
        let outcome = self.validate_custom_model(model, force_full).outcome;
        CustomArtifactValidationSummary {
            artifact_id: model.model_id.clone(),
            kind: ArtifactKind::Model,
            trust_kind: ModelTrustKind::UserSupplied,
            installation_status: outcome.status,
            expected_bytes: model.asset_bytes,
            expected_sha256: model.asset_sha256.clone(),
            observed_bytes: outcome.observed_bytes,
            observed_sha256: outcome.observed_sha256,
            validation_code: outcome.code.into(),
            verified_unix_ms: now_unix_ms(),
        }
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

    fn validate_runtime(&self, runtime: &ApprovedRuntimeArtifact) -> SourcedValidationOutcome {
        let mut large_asset_source = ValidationSource::Hashed;
        let cached_asset = runtime
            .required_files
            .iter()
            .max_by_key(|file| file.bytes)
            .map(|file| file.relative_path.as_str());
        let outcome = (|| {
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
                let validated = if Some(required.relative_path.as_str()) == cached_asset {
                    self.validation_cache.hash_or_reuse(
                        &file_path,
                        &required.sha256,
                        &self.catalog_digest,
                        force_full_validation(),
                        sha256_file,
                    )
                } else {
                    sha256_file(&file_path).map(|observed_sha256| {
                        crate::artifact_validation_cache::ValidatedHash {
                            observed_sha256,
                            source: ValidationSource::Hashed,
                        }
                    })
                };
                if Some(required.relative_path.as_str()) == cached_asset {
                    if let Ok(validated) = &validated {
                        large_asset_source = validated.source;
                    }
                }
                match validated {
                    Ok(validated) if validated.observed_sha256 == required.sha256 => {}
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
            let license_bytes =
                match source_controlled_runtime_license_bytes(&runtime.license_asset) {
                    Ok(bytes) => bytes,
                    Err(_) => {
                        return ValidationOutcome {
                            status: InstallationStatus::InvalidPath,
                            observed_bytes: None,
                            observed_sha256: None,
                            code: "invalid_license_asset",
                        }
                    }
                };
            let license_path = match resolve_contained(
                &package_dir,
                &runtime.license_asset.destination_relative_path,
            ) {
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
            listed.insert(
                runtime
                    .license_asset
                    .destination_relative_path
                    .to_ascii_lowercase(),
            );
            let license_metadata = match license_path.metadata() {
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
            if reject_reparse_point(&license_path).is_err() {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                };
            }
            if license_metadata.len() != runtime.license_asset.bytes
                || license_bytes.len() as u64 != runtime.license_asset.bytes
            {
                return ValidationOutcome {
                    status: InstallationStatus::BytesMismatch,
                    observed_bytes: Some(license_metadata.len()),
                    observed_sha256: None,
                    code: "bytes_mismatch",
                };
            }
            match sha256_file(&license_path) {
                Ok(hash) if hash == runtime.license_asset.sha256 => {}
                Ok(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::HashMismatch,
                        observed_bytes: Some(license_metadata.len()),
                        observed_sha256: None,
                        code: "hash_mismatch",
                    }
                }
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::IoError,
                        observed_bytes: Some(license_metadata.len()),
                        observed_sha256: None,
                        code: "io_error",
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
        })();
        SourcedValidationOutcome {
            outcome,
            source: large_asset_source,
        }
    }

    fn validate_managed_model(
        &self,
        model: &ManagedModelArtifact,
        force_full: bool,
    ) -> SourcedValidationOutcome {
        match model {
            ManagedModelArtifact::Approved(model) => {
                self.validate_model_with_force(model, force_full)
            }
            ManagedModelArtifact::Custom(model) => self.validate_custom_model(model, force_full),
        }
    }

    fn validate_model(&self, model: &ApprovedModelArtifact) -> SourcedValidationOutcome {
        self.validate_model_with_force(model, force_full_validation())
    }

    fn validate_model_with_force(
        &self,
        model: &ApprovedModelArtifact,
        force_full: bool,
    ) -> SourcedValidationOutcome {
        self.validate_model_file(
            &model.managed_relative_path,
            model.asset_bytes,
            &model.asset_sha256,
            force_full,
        )
    }

    fn resolve_custom_model_gguf(&self, model: &CustomModelArtifact) -> String {
        let custom_dir = self
            .roots
            .model_root
            .join(format!("custom/{}", model.model_id));
        if let Ok(entries) = std::fs::read_dir(&custom_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_file() {
                    if let Some(ext) = path.extension() {
                        let ext_str = ext.to_string_lossy().to_lowercase();
                        if ext_str == "gguf" {
                            let filename = path.file_name().unwrap_or_default().to_string_lossy();
                            return format!("custom/{}/{}", model.model_id, filename);
                        }
                    }
                }
            }
        }
        model.managed_relative_path.clone()
    }

    fn validate_custom_model(
        &self,
        model: &CustomModelArtifact,
        force_full: bool,
    ) -> SourcedValidationOutcome {
        let actual_relative_path = self.resolve_custom_model_gguf(model);
        self.validate_model_file(
            &actual_relative_path,
            model.asset_bytes,
            &model.asset_sha256,
            force_full,
        )
    }

    fn validate_model_file(
        &self,
        managed_relative_path: &str,
        expected_bytes: u64,
        expected_sha256: &str,
        force_full: bool,
    ) -> SourcedValidationOutcome {
        let mut source = ValidationSource::Hashed;
        let outcome = (|| {
            let path = match resolve_contained(&self.roots.model_root, managed_relative_path) {
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
            if metadata.len() != expected_bytes {
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
            match self.validation_cache.hash_or_reuse(
                &path,
                expected_sha256,
                &self.catalog_digest,
                force_full,
                sha256_file,
            ) {
                Ok(validated) if validated.observed_sha256 == expected_sha256 => {
                    source = validated.source;
                    ValidationOutcome {
                        status: InstallationStatus::Valid,
                        observed_bytes: Some(metadata.len()),
                        observed_sha256: Some(validated.observed_sha256),
                        code: "valid",
                    }
                }
                Ok(validated) => {
                    source = validated.source;
                    ValidationOutcome {
                        status: InstallationStatus::HashMismatch,
                        observed_bytes: Some(metadata.len()),
                        observed_sha256: Some(validated.observed_sha256),
                        code: "hash_mismatch",
                    }
                }
                Err(_) => ValidationOutcome {
                    status: InstallationStatus::IoError,
                    observed_bytes: Some(metadata.len()),
                    observed_sha256: None,
                    code: "io_error",
                },
            }
        })();
        SourcedValidationOutcome { outcome, source }
    }
}

fn normalize_catalog_line_endings(bytes: &[u8]) -> Result<Cow<'_, [u8]>, ArtifactTrustError> {
    if !bytes.contains(&b'\r') {
        return Ok(Cow::Borrowed(bytes));
    }

    let mut normalized = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'\r' {
            if bytes.get(index + 1) != Some(&b'\n') {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "catalog line endings rejected",
                ));
            }
            normalized.push(b'\n');
            index += 2;
        } else {
            normalized.push(bytes[index]);
            index += 1;
        }
    }
    Ok(Cow::Owned(normalized))
}

fn canonical_catalog_bytes(bytes: &[u8]) -> Result<Cow<'_, [u8]>, ArtifactTrustError> {
    let normalized = normalize_catalog_line_endings(bytes)?;
    if sha256_bytes(normalized.as_ref()) != EMBEDDED_CATALOG_SHA256 {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "embedded catalog identity rejected",
        ));
    }
    Ok(normalized)
}

fn canonical_embedded_catalog_bytes() -> Result<Cow<'static, [u8]>, ArtifactTrustError> {
    canonical_catalog_bytes(CATALOG_BYTES)
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
pub async fn managed_installed_artifacts(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> Result<ManagedInstalledArtifacts, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state.installed_artifacts();
        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!("[PERF] cmd=managed_installed_artifacts dur_ms={dur_ms}");
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "installed artifacts worker failed"))
}

#[tauri::command]
pub async fn get_model_storage_info(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> Result<ModelStorageInfo, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || state.model_storage_info())
        .await
        .map_err(|_| BridgeError::new("runtime_unavailable", "model storage worker failed"))
}

#[tauri::command]
pub fn open_model_storage_folder(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> Result<(), BridgeError> {
    let path = &state.roots().model_root;
    #[cfg(windows)]
    let result = std::process::Command::new("explorer.exe").arg(path).spawn();
    #[cfg(target_os = "macos")]
    let result = std::process::Command::new("open").arg(path).spawn();
    #[cfg(all(unix, not(target_os = "macos")))]
    let result = std::process::Command::new("xdg-open").arg(path).spawn();
    result.map(|_| ()).map_err(|_| {
        BridgeError::new(
            "storage_open_failed",
            "model storage folder could not be opened",
        )
    })
}

#[tauri::command]
pub async fn managed_artifact_trust_bundle(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> Result<ManagedArtifactTrustBundle, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state.artifact_trust_bundle();

        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!("[PERF] cmd=managed_artifact_trust_bundle dur_ms={dur_ms}");
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "artifact trust worker failed"))
}

#[tauri::command]
pub async fn managed_artifact_validation_status(
    state: State<'_, Arc<ArtifactTrustService>>,
    artifact_id: String,
) -> Result<ArtifactValidationSummary, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state
            .artifact_validation_status(&artifact_id)
            .map_err(BridgeError::from);
        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!(
                "[PERF] cmd=managed_artifact_validation_status artifact={artifact_id} dur_ms={dur_ms}"
            );
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "artifact validation worker failed"))?
}

#[tauri::command]
pub async fn managed_model_readiness(
    state: State<'_, Arc<ArtifactTrustService>>,
    model_id: String,
) -> Result<ModelReadinessSummary, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state.model_readiness(&model_id).map_err(BridgeError::from);
        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!("[PERF] cmd=managed_model_readiness model={model_id} dur_ms={dur_ms}");
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model readiness worker failed"))?
}

pub(crate) fn validate_custom_huggingface_url(
    value: &str,
) -> Result<ValidatedCustomModelSource, ArtifactTrustError> {
    if value.is_empty()
        || value.len() > 2_048
        || !value.is_ascii()
        || value.bytes().any(|byte| byte.is_ascii_control())
        || value.contains(['%', '\\'])
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_url",
            "custom Hugging Face URL rejected",
        ));
    }
    let url = Url::parse(value).map_err(|_| {
        ArtifactTrustError::new("invalid_custom_url", "custom Hugging Face URL rejected")
    })?;
    if url.as_str() != value
        || url.scheme() != "https"
        || url.host_str() != Some("huggingface.co")
        || url.port().is_some()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_url",
            "custom Hugging Face URL rejected",
        ));
    }
    let segments: Vec<&str> = url.path_segments().map(Iterator::collect).ok_or_else(|| {
        ArtifactTrustError::new("invalid_custom_url", "custom Hugging Face path rejected")
    })?;
    if segments.len() < 5 || segments[2] != "resolve" {
        return Err(ArtifactTrustError::new(
            "invalid_custom_url",
            "custom Hugging Face resolve path required",
        ));
    }
    for segment in &segments {
        validate_custom_url_segment(segment)?;
    }
    let owner = segments[0];
    let repository = segments[1];
    let revision = segments[3];
    let filename = *segments.last().ok_or_else(|| {
        ArtifactTrustError::new("invalid_custom_url", "custom model filename missing")
    })?;
    if owner.len() > 96
        || repository.len() > 96
        || revision.len() > 128
        || filename.len() > 128
        || !filename.ends_with(".gguf")
        || validate_filename(filename).is_err()
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_url",
            "custom model URL fields rejected",
        ));
    }
    let source_repository = format!("{owner}/{repository}");
    let model_id = format!("{CUSTOM_MODEL_ID_PREFIX}{}", sha256_bytes(value.as_bytes()));
    validate_artifact_id(&model_id)?;
    let managed_relative_path = format!("custom/{model_id}/{filename}");
    validate_relative_windows_path(&managed_relative_path)?;
    Ok(ValidatedCustomModelSource {
        model_id,
        display_name: filename.to_string(),
        source_url: value.to_string(),
        source_repository,
        source_revision: revision.to_string(),
        asset_filename: filename.to_string(),
        compatible_runtime_ids: vec![
            CUSTOM_MODEL_RUNTIME_ID.to_string(),
            VULKAN_MODEL_RUNTIME_ID.to_string(),
        ],
        managed_relative_path,
    })
}

fn validate_local_import_source(
    value: &str,
    expected_asset_sha256: &str,
) -> Result<ValidatedCustomModelSource, ArtifactTrustError> {
    validate_sha256(expected_asset_sha256)?;
    let prefix = "local://import/";
    let suffix = value.strip_prefix(prefix).ok_or_else(|| {
        ArtifactTrustError::new("invalid_custom_source", "local import source rejected")
    })?;
    if value.len() > 2_048
        || !value.is_ascii()
        || value.bytes().any(|byte| byte.is_ascii_control())
        || value.contains(['%', '\\'])
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_source",
            "local import source rejected",
        ));
    }
    let Some((asset_sha256, filename)) = suffix.split_once('/') else {
        return Err(ArtifactTrustError::new(
            "invalid_custom_source",
            "local import source rejected",
        ));
    };
    if suffix.matches('/').count() != 1
        || asset_sha256 != expected_asset_sha256
        || validate_sha256(asset_sha256).is_err()
        || validate_filename(filename).is_err()
        || !filename.ends_with(".gguf")
        || value != format!("{prefix}{asset_sha256}/{filename}")
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_source",
            "local import source rejected",
        ));
    }
    let model_id = format!("{CUSTOM_MODEL_ID_PREFIX}{}", sha256_bytes(value.as_bytes()));
    validate_artifact_id(&model_id)?;
    let managed_relative_path = format!("custom/{model_id}/{filename}");
    validate_relative_windows_path(&managed_relative_path)?;
    Ok(ValidatedCustomModelSource {
        model_id,
        display_name: filename.to_string(),
        source_url: value.to_string(),
        source_repository: "local/import".to_string(),
        source_revision: asset_sha256.to_string(),
        asset_filename: filename.to_string(),
        compatible_runtime_ids: vec![
            CUSTOM_MODEL_RUNTIME_ID.to_string(),
            VULKAN_MODEL_RUNTIME_ID.to_string(),
        ],
        managed_relative_path,
    })
}

fn validate_custom_model_source(
    source_url: &str,
    asset_sha256: &str,
) -> Result<ValidatedCustomModelSource, ArtifactTrustError> {
    if source_url.starts_with("https://") {
        validate_custom_huggingface_url(source_url)
    } else {
        validate_local_import_source(source_url, asset_sha256)
    }
}

fn validate_custom_url_segment(segment: &str) -> Result<(), ArtifactTrustError> {
    if segment.is_empty()
        || segment.len() > 128
        || segment == "."
        || segment == ".."
        || !segment
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_alphanumeric())
        || segment.bytes().any(|byte| {
            !(byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'+' | b'-'))
        })
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_url",
            "custom Hugging Face path segment rejected",
        ));
    }
    Ok(())
}

fn ensure_managed_directories(roots: &ManagedArtifactRoots) -> Result<(), ArtifactTrustError> {
    for path in [
        roots.model_root.join("custom"),
        roots.model_root.join("approved"),
        roots.runtime_root.clone(),
        roots.state_root.clone(),
        roots.app_data_root.join("state"),
        roots.app_data_root.join("logs"),
    ] {
        fs::create_dir_all(&path).map_err(|_| {
            ArtifactTrustError::new(
                "managed_storage_unavailable",
                "managed LocalComet storage could not be created",
            )
        })?;
    }
    Ok(())
}

fn directory_file_bytes(root: &Path) -> u64 {
    let mut total = 0_u64;
    let mut pending = vec![root.to_path_buf()];
    while let Some(path) = pending.pop() {
        let Ok(entries) = fs::read_dir(path) else {
            continue;
        };
        for entry in entries.flatten() {
            let Ok(metadata) = entry.metadata() else {
                continue;
            };
            if metadata.is_file() {
                total = total.saturating_add(metadata.len());
            } else if metadata.is_dir() && !metadata.file_type().is_symlink() {
                pending.push(entry.path());
            }
        }
    }
    total
}

#[cfg(windows)]
fn available_space(path: &Path) -> Option<u64> {
    let mut available = 0_u64;
    let mut total = 0_u64;
    let mut free = 0_u64;
    let mut wide: Vec<u16> = path
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let result =
        unsafe { GetDiskFreeSpaceExW(wide.as_mut_ptr(), &mut available, &mut total, &mut free) };
    (result != 0).then_some(available)
}

#[cfg(not(windows))]
fn available_space(_path: &Path) -> Option<u64> {
    None
}

fn custom_manifest_path(roots: &ManagedArtifactRoots) -> Result<PathBuf, ArtifactTrustError> {
    resolve_contained(&roots.state_root, CUSTOM_MANIFEST_FILENAME)
}

fn load_custom_manifest(
    roots: &ManagedArtifactRoots,
    catalog: &ApprovedArtifactCatalog,
) -> Result<CustomModelManifest, ArtifactTrustError> {
    let path = custom_manifest_path(roots)?;
    let metadata = match fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(CustomModelManifest::default())
        }
        Err(_) => {
            return Err(ArtifactTrustError::new(
                "invalid_custom_manifest",
                "custom model manifest metadata unavailable",
            ))
        }
    };
    let _guards = open_directory_guard_chain(&roots.app_data_root, &roots.state_root, false)?;
    if !metadata.is_file()
        || metadata.len() > MAX_CUSTOM_MANIFEST_BYTES
        || ensure_existing_safe_path(&roots.app_data_root, &roots.state_root, &path, false).is_err()
    {
        return Err(ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest rejected",
        ));
    }
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    File::open(&path)
        .map_err(|_| {
            ArtifactTrustError::new(
                "invalid_custom_manifest",
                "custom model manifest unavailable",
            )
        })?
        .take(MAX_CUSTOM_MANIFEST_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| {
            ArtifactTrustError::new(
                "invalid_custom_manifest",
                "custom model manifest unreadable",
            )
        })?;
    if bytes.len() as u64 > MAX_CUSTOM_MANIFEST_BYTES {
        return Err(ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest exceeds size limit",
        ));
    }
    let manifest = parse_custom_manifest(&bytes)?;
    validate_custom_manifest(&manifest, catalog)?;
    Ok(manifest)
}

fn parse_custom_manifest(bytes: &[u8]) -> Result<CustomModelManifest, ArtifactTrustError> {
    if bytes.starts_with(&[0xef, 0xbb, 0xbf]) {
        return Err(ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest BOM rejected",
        ));
    }
    let mut deserializer = serde_json::Deserializer::from_slice(bytes);
    let unique = UniqueValue::deserialize(&mut deserializer).map_err(|_| {
        ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest JSON rejected",
        )
    })?;
    deserializer.end().map_err(|_| {
        ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest trailing data rejected",
        )
    })?;
    serde_json::from_value(unique.0).map_err(|_| {
        ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest schema rejected",
        )
    })
}

/// Custom manifest compatibility check. Current imports record both the CPU
/// and the Vulkan runtime. Manifests written before the Vulkan runtime was
/// added to custom imports record only the CPU runtime; accepting that exact
/// legacy shape keeps every previously imported custom model loadable instead
/// of silently dropping the whole manifest (strictly narrower, no widening).
fn custom_compatible_runtimes_match(source: &[String], stored: &[String]) -> bool {
    if source == stored {
        return true;
    }
    stored.len() == 1
        && stored.first().map(String::as_str) == Some(CUSTOM_MODEL_RUNTIME_ID)
        && source.last().map(String::as_str) == Some(VULKAN_MODEL_RUNTIME_ID)
}

fn validate_custom_manifest(
    manifest: &CustomModelManifest,
    catalog: &ApprovedArtifactCatalog,
) -> Result<(), ArtifactTrustError> {
    if manifest.schema_version != SCHEMA_VERSION || manifest.models.len() > MAX_CUSTOM_MODELS {
        return Err(ArtifactTrustError::new(
            "invalid_custom_manifest",
            "custom model manifest header rejected",
        ));
    }
    let mut previous_id = None::<&str>;
    let mut ids = BTreeSet::new();
    let mut paths = BTreeSet::new();
    let mut sources = BTreeSet::new();
    for model in &manifest.models {
        validate_artifact_id(&model.model_id)?;
        if previous_id.is_some_and(|previous| previous >= model.model_id.as_str())
            || !ids.insert(model.model_id.as_str())
            || catalog
                .models
                .iter()
                .any(|approved| approved.model_id == model.model_id)
            || catalog
                .runtimes
                .iter()
                .any(|approved| approved.runtime_id == model.model_id)
        {
            return Err(ArtifactTrustError::new(
                "invalid_custom_manifest",
                "custom model ids are not unique and sorted",
            ));
        }
        previous_id = Some(&model.model_id);
        let source = validate_custom_model_source(&model.source_url, &model.asset_sha256)?;
        if source.model_id != model.model_id
            || source.display_name != model.display_name
            || source.source_repository != model.source_repository
            || source.source_revision != model.source_revision
            || source.asset_filename != model.asset_filename
            || !custom_compatible_runtimes_match(
                &source.compatible_runtime_ids,
                &model.compatible_runtime_ids,
            )
            || source.managed_relative_path != model.managed_relative_path
            || model.asset_bytes == 0
            || model.asset_bytes > MAX_MODEL_BYTES
            || validate_sha256(&model.asset_sha256).is_err()
            || !paths.insert(model.managed_relative_path.to_ascii_lowercase())
            || !sources.insert(model.source_url.as_str())
        {
            return Err(ArtifactTrustError::new(
                "invalid_custom_manifest",
                "custom model record rejected",
            ));
        }
        ensure_sorted_unique(
            model
                .compatible_runtime_ids
                .iter()
                .map(|runtime_id| runtime_id.as_str()),
        )?;
        for runtime_id in &model.compatible_runtime_ids {
            if !catalog
                .runtimes
                .iter()
                .any(|runtime| &runtime.runtime_id == runtime_id)
            {
                return Err(ArtifactTrustError::new(
                    "invalid_custom_manifest",
                    "custom model runtime is not approved",
                ));
            }
        }
    }
    Ok(())
}

fn persist_custom_manifest(
    roots: &ManagedArtifactRoots,
    manifest: &CustomModelManifest,
) -> Result<(), ArtifactTrustError> {
    let mut bytes = serde_json::to_vec_pretty(manifest).map_err(|_| {
        ArtifactTrustError::new(
            "custom_manifest_persist_failed",
            "custom model manifest serialization failed",
        )
    })?;
    bytes.push(b'\n');
    if bytes.len() as u64 > MAX_CUSTOM_MANIFEST_BYTES {
        return Err(ArtifactTrustError::new(
            "custom_manifest_persist_failed",
            "custom model manifest exceeds size limit",
        ));
    }
    let _guards = open_directory_guard_chain(&roots.app_data_root, &roots.state_root, true)?;
    let destination = custom_manifest_path(roots)?;
    if destination.exists()
        && ensure_existing_safe_path(&roots.app_data_root, &roots.state_root, &destination, false)
            .is_err()
    {
        return Err(ArtifactTrustError::new(
            "custom_manifest_persist_failed",
            "custom model manifest destination rejected",
        ));
    }
    let sequence = CUSTOM_MANIFEST_TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed);
    let temporary_name = format!("custom-models.v1.{}.{}.tmp", std::process::id(), sequence);
    let temporary = resolve_contained(&roots.state_root, &temporary_name)?;
    let write_result = (|| -> std::io::Result<()> {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)?;
        file.write_all(&bytes)?;
        file.sync_all()?;
        atomic_replace_file(&temporary, &destination)
    })();
    if write_result.is_err() {
        let _ = fs::remove_file(&temporary);
        return Err(ArtifactTrustError::new(
            "custom_manifest_persist_failed",
            "custom model manifest durable replace failed",
        ));
    }
    Ok(())
}

#[cfg(windows)]
fn atomic_replace_file(temporary: &Path, destination: &Path) -> std::io::Result<()> {
    if !destination.exists() {
        return fs::rename(temporary, destination);
    }
    let replacement: Vec<u16> = destination
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let temporary: Vec<u16> = temporary
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let result = unsafe {
        MoveFileExW(
            temporary.as_ptr(),
            replacement.as_ptr(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
    };
    if result == 0 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(())
    }
}

#[cfg(not(windows))]
fn atomic_replace_file(temporary: &Path, destination: &Path) -> std::io::Result<()> {
    fs::rename(temporary, destination)
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
    let mut acquisition_sources = BTreeSet::new();

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
            || !matches!(runtime.variant.as_str(), "cpu" | "vulkan")
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
        validate_acquisition(
            &runtime.acquisition,
            ExpectedAcquisition {
                artifact_id: &runtime.runtime_id,
                artifact_kind: AcquisitionArtifactKind::Runtime,
                filename: &runtime.asset_filename,
                bytes: runtime.asset_bytes,
                sha256: &runtime.asset_sha256,
                destination: &runtime.managed_relative_path,
            },
            &mut acquisition_sources,
        )?;
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
            } else if !required
                .relative_path
                .to_ascii_lowercase()
                .ends_with(".dll")
            {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime installable file type rejected",
                ));
            }
        }
        if !executable_found {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime executable identity missing",
            ));
        }
        if runtime.license_asset.source_relative_path != LLAMA_CPP_LICENSE_SOURCE_PATH
            || runtime.license_asset.destination_relative_path != "LICENSE-MIT.txt"
            || runtime.license_asset.bytes == 0
            || validate_relative_windows_path(&runtime.license_asset.destination_relative_path)
                .is_err()
            || validate_sha256(&runtime.license_asset.sha256).is_err()
            || source_controlled_runtime_license_bytes(&runtime.license_asset).is_err()
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime license asset rejected",
            ));
        }
        let license_destination = runtime
            .license_asset
            .destination_relative_path
            .to_ascii_lowercase();
        if file_paths.contains(&license_destination) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime license destination overlaps installable file",
            ));
        }
        if runtime.archive_members.is_empty()
            || runtime.archive_members.len() > MAX_RUNTIME_ARCHIVE_MEMBERS
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime archive member list rejected",
            ));
        }
        let mut archive_paths = BTreeSet::new();
        let mut archive_install_paths = BTreeSet::new();
        let mut archive_previous = None::<String>;
        for member in &runtime.archive_members {
            validate_relative_windows_path(&member.relative_path)?;
            let folded = member.relative_path.to_ascii_lowercase();
            if archive_previous
                .as_ref()
                .is_some_and(|value| value >= &folded || folded.starts_with(&format!("{value}/")))
                || !archive_paths.insert(folded.clone())
            {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime archive members not sorted or unique",
                ));
            }
            archive_previous = Some(folded.clone());
            match member.disposition {
                RuntimeArchiveMemberDisposition::Install => {
                    if !file_paths.contains(&folded) || !archive_install_paths.insert(folded) {
                        return Err(ArtifactTrustError::new(
                            "invalid_catalog",
                            "runtime install disposition rejected",
                        ));
                    }
                }
                RuntimeArchiveMemberDisposition::RecognizedNotInstalled => {
                    if file_paths.contains(&folded)
                        || folded == runtime.executable_relative_path.to_ascii_lowercase()
                        || !folded.ends_with(".exe")
                    {
                        return Err(ArtifactTrustError::new(
                            "invalid_catalog",
                            "runtime recognized member disposition rejected",
                        ));
                    }
                }
            }
        }
        if archive_install_paths != file_paths {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime archive install set mismatch",
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
        validate_acquisition(
            &model.acquisition,
            ExpectedAcquisition {
                artifact_id: &model.model_id,
                artifact_kind: AcquisitionArtifactKind::Model,
                filename: &model.asset_filename,
                bytes: model.asset_bytes,
                sha256: &model.asset_sha256,
                destination: &model.managed_relative_path,
            },
            &mut acquisition_sources,
        )?;
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

struct ExpectedAcquisition<'a> {
    artifact_id: &'a str,
    artifact_kind: AcquisitionArtifactKind,
    filename: &'a str,
    bytes: u64,
    sha256: &'a str,
    destination: &'a str,
}

fn validate_acquisition(
    acquisition: &ApprovedArtifactAcquisition,
    expected: ExpectedAcquisition<'_>,
    identities: &mut BTreeSet<String>,
) -> Result<(), ArtifactTrustError> {
    validate_artifact_id(&acquisition.artifact_id)?;
    if acquisition.artifact_id != expected.artifact_id
        || acquisition.artifact_kind != expected.artifact_kind
        || acquisition.source_type != AcquisitionSourceType::ApprovedHttps
        || acquisition.expected_filename != expected.filename
        || acquisition.expected_bytes != expected.bytes
        || acquisition.expected_sha256 != expected.sha256
        || acquisition.managed_relative_destination != expected.destination
        || acquisition.public_distribution
        || acquisition.installer_bundled
        || acquisition.automatic_download
        || !acquisition.user_confirmation_required
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "acquisition identity rejected",
        ));
    }
    validate_filename(&acquisition.expected_filename)?;
    validate_sha256(&acquisition.expected_sha256)?;
    validate_relative_windows_path(&acquisition.managed_relative_destination)?;
    if acquisition.expected_bytes == 0
        || acquisition.allowed_redirect_hosts.is_empty()
        || acquisition.allowed_redirect_hosts.len() > 16
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "acquisition metadata rejected",
        ));
    }
    let mut prior_host = None::<&str>;
    for host in &acquisition.allowed_redirect_hosts {
        validate_allowed_redirect_host(host)?;
        if prior_host.is_some_and(|prior| prior >= host.as_str()) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "redirect hosts not sorted or unique",
            ));
        }
        prior_host = Some(host);
    }
    let primary_host = validate_https_url(&acquisition.primary_url)?;
    if !acquisition
        .allowed_redirect_hosts
        .iter()
        .any(|host| host == primary_host)
        || !identities.insert(acquisition.primary_url.clone())
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "acquisition source rejected",
        ));
    }
    if let Some(content_type) = &acquisition.content_type {
        if content_type.is_empty()
            || content_type.len() > 128
            || content_type.chars().any(|character| {
                character.is_control()
                    || !(character.is_ascii_alphanumeric()
                        || matches!(character, '/' | '-' | '+' | '.' | ';' | '=' | ' '))
            })
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "acquisition content type rejected",
            ));
        }
    }
    Ok(())
}

fn validate_allowed_redirect_host(value: &str) -> Result<(), ArtifactTrustError> {
    if value.is_empty()
        || value.len() > 253
        || value.starts_with('.')
        || value.ends_with('.')
        || !value.contains('.')
        || value.bytes().any(|byte| {
            !(byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'.' | b'-'))
        })
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "redirect host rejected",
        ));
    }
    Ok(())
}

fn validate_https_url(value: &str) -> Result<&str, ArtifactTrustError> {
    if value.len() > 2_048
        || value.chars().any(char::is_control)
        || !value.starts_with("https://")
        || value.contains(['?', '#', '@', '\\'])
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "HTTPS URL rejected",
        ));
    }
    let after_scheme = &value["https://".len()..];
    let Some((host, path)) = after_scheme.split_once('/') else {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "HTTPS URL path rejected",
        ));
    };
    validate_allowed_redirect_host(host)?;
    if path.is_empty() {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "HTTPS URL path rejected",
        ));
    }
    Ok(host)
}

fn validate_required_texts(values: &[&str]) -> Result<(), ArtifactTrustError> {
    if values.iter().any(|value| {
        value.trim().is_empty() || value.len() > 256 || value.chars().any(char::is_control)
    }) {
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
    if value.contains('/')
        || !value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_alphanumeric())
    {
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
        || value.bytes().any(|byte| {
            !(byte.is_ascii_alphanumeric() || matches!(byte, b'/' | b'.' | b'_' | b'+' | b'-'))
        })
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

pub(crate) fn resolve_contained(
    root: &Path,
    relative: &str,
) -> Result<PathBuf, ArtifactTrustError> {
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

fn open_directory_guard_chain(
    root: &Path,
    target: &Path,
    create_missing: bool,
) -> Result<Vec<File>, ArtifactTrustError> {
    let relative = target
        .strip_prefix(root)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed directory escaped root"))?;
    let root_metadata = fs::symlink_metadata(root)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "app data root unavailable"))?;
    if !root_metadata.is_dir() {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "app data root type rejected",
        ));
    }
    reject_reparse_point(root)?;
    let mut handles = vec![open_directory_guard(root)?];
    let mut current = root.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if !metadata.is_dir() {
                    return Err(ArtifactTrustError::new(
                        "invalid_path",
                        "managed directory type rejected",
                    ));
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound && create_missing => {
                if let Err(create_error) = fs::create_dir(&current) {
                    if create_error.kind() != std::io::ErrorKind::AlreadyExists {
                        return Err(ArtifactTrustError::new(
                            "io_error",
                            "managed directory creation failed",
                        ));
                    }
                }
                let metadata = fs::symlink_metadata(&current).map_err(|_| {
                    ArtifactTrustError::new("invalid_path", "managed directory unavailable")
                })?;
                if !metadata.is_dir() {
                    return Err(ArtifactTrustError::new(
                        "invalid_path",
                        "managed directory type rejected",
                    ));
                }
            }
            Err(_) => {
                return Err(ArtifactTrustError::new(
                    "invalid_path",
                    "managed directory unavailable",
                ))
            }
        }
        reject_reparse_point(&current)?;
        handles.push(open_directory_guard(&current)?);
    }
    Ok(handles)
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

#[cfg(windows)]
fn open_directory_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    let wide: Vec<u16> = path
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let handle = unsafe {
        CreateFileW(
            wide.as_ptr(),
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            std::ptr::null(),
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            std::ptr::null_mut(),
        )
    };
    if handle.is_null() || handle == INVALID_HANDLE_VALUE {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "directory identity guard failed",
        ));
    }
    let file = unsafe { File::from_raw_handle(handle.cast()) };
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
    let metadata = file
        .metadata()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "directory metadata unavailable"))?;
    if !metadata.is_dir() || metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "directory identity rejected",
        ));
    }
    Ok(file)
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

#[cfg(not(windows))]
fn open_directory_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    reject_reparse_point(path)?;
    let file = File::open(path)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "directory identity guard failed"))?;
    if !file
        .metadata()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "directory metadata unavailable"))?
        .is_dir()
    {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "directory identity rejected",
        ));
    }
    Ok(file)
}

fn sha256_file(path: &Path) -> Result<String, ArtifactTrustError> {
    let start = std::time::Instant::now();
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
    let result = format!("{:x}", hasher.finalize());
    let dur_ms = start.elapsed().as_millis();
    if perf_logging_enabled() {
        eprintln!("[PERF] sha256_file path={} dur_ms={dur_ms}", path.display());
    }
    Ok(result)
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub(crate) fn perf_logging_enabled() -> bool {
    perf_logging_enabled_from(std::env::var("LOCALCOMET_PERF").ok().as_deref())
}

fn perf_logging_enabled_from(value: Option<&str>) -> bool {
    value == Some("1")
}

pub(crate) fn force_full_validation() -> bool {
    force_full_validation_from(
        std::env::var("LOCALCOMET_FORCE_FULL_VALIDATION")
            .ok()
            .as_deref(),
    )
}

fn force_full_validation_from(value: Option<&str>) -> bool {
    value == Some("1")
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

#[tauri::command]
pub async fn import_custom_model(
    state: tauri::State<'_, Arc<ArtifactTrustService>>,
    approval_state: tauri::State<'_, Arc<crate::ApprovalState>>,
    source_path: String,
    filename: String,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<String, String> {
    let source = std::path::PathBuf::from(&source_path);
    let source_metadata = std::fs::symlink_metadata(&source)
        .map_err(|e| format!("Source file metadata unavailable: {e}"))?;
    if !source_metadata.is_file() || source_metadata.file_type().is_symlink() {
        return Err("Source must be a regular non-symlink file".to_string());
    }
    if source_metadata.len() > MAX_MODEL_BYTES {
        return Err(format!(
            "Source file exceeds the {} byte limit",
            MAX_MODEL_BYTES
        ));
    }

    crate::approval_commands::validate_approval_token(
        &approval_state,
        "import_custom_model",
        &serde_json::json!({
            "source_path": source_path,
            "filename": filename
        }),
        &token,
        &approval_id,
        &call_id,
    )
    .map_err(|e| e.code.to_string())?;

    let safe_filename = std::path::Path::new(&filename)
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or("Invalid filename")?
        .to_string();

    let state_clone = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let source_sha256 = crate::artifact_trust::sha256_file(&source)
            .map_err(|error| error.code().to_string())?;
        let source_url = format!("local://import/{source_sha256}/{safe_filename}");
        let source_metadata =
            crate::artifact_trust::validate_local_import_source(&source_url, &source_sha256)
                .map_err(|error| error.code().to_string())?;
        let model_id = source_metadata.model_id.clone();
        if state_clone
            .custom_model(&model_id)
            .map_err(|error| error.code().to_string())?
            .is_some()
        {
            return Ok(model_id);
        }
        state_clone
            .ensure_custom_model_capacity(&model_id)
            .map_err(|error| error.code().to_string())?;
        let dest_path = crate::artifact_trust::resolve_contained(
            &state_clone.roots.model_root,
            &source_metadata.managed_relative_path,
        )
        .map_err(|error| error.code().to_string())?;
        if dest_path.exists() {
            return Err("custom_model_destination_exists".to_string());
        }
        std::fs::create_dir_all(dest_path.parent().ok_or("invalid_custom_destination")?)
            .map_err(|error| error.to_string())?;

        std::fs::copy(&source, &dest_path).map_err(|e| e.to_string())?;

        let bytes = match std::fs::metadata(&dest_path) {
            Ok(meta) => meta.len(),
            Err(e) => {
                let _ = std::fs::remove_file(&dest_path);
                return Err(e.to_string());
            }
        };
        if bytes > MAX_MODEL_BYTES {
            let _ = std::fs::remove_file(&dest_path);
            return Err("custom_model_too_large".to_string());
        }
        let sha256 = match crate::artifact_trust::sha256_file(&dest_path) {
            Ok(hash) => hash,
            Err(e) => {
                let _ = std::fs::remove_file(&dest_path);
                return Err(e.code().to_string());
            }
        };
        if sha256 != source_sha256 {
            let _ = std::fs::remove_file(&dest_path);
            return Err("custom_model_source_changed".to_string());
        }

        let model = source_metadata.into_artifact(bytes, sha256);

        if let Err(e) = state_clone.register_custom_model_after_validation(model) {
            let _ = std::fs::remove_file(&dest_path);
            return Err(e.code().to_string());
        }

        Ok(model_id)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[cfg(test)]
#[path = "artifact_trust_tests.rs"]
mod tests;
