//! Test module extracted from `artifact_trust.rs` during the 2026-09-02 refactor.
//! Content is verbatim; paths inside (`super::`, `crate::`) are unchanged.

use super::*;
// COPIED-IMPORTS: parent use-bindings (private imports are not glob-visible)
use crate::artifact_validation_cache::ValidationSource;
use serde_json::Value;
use std::borrow::Cow;
use std::fs::OpenOptions;
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicU64;
use std::sync::atomic::Ordering;
use std::sync::Arc;

const TEST_RUNTIME_BYTES: &[u8] = b"test-runtime";
const TEST_MODEL_BYTES: &[u8] = b"GGUFtest-model";

static TEST_SEQUENCE: AtomicU64 = AtomicU64::new(0);

#[test]
fn perf_logging_gates_on_localcomet_perf_flag() {
    assert!(perf_logging_enabled_from(Some("1")));
    assert!(!perf_logging_enabled_from(Some("0")));
    assert!(!perf_logging_enabled_from(None));
    assert!(!perf_logging_enabled_from(Some("true")));
    assert!(!perf_logging_enabled_from(Some("")));
    assert!(!perf_logging_enabled_from(Some("11")));
}

#[test]
fn force_full_validation_gates_only_on_exact_one() {
    assert!(force_full_validation_from(Some("1")));
    assert!(!force_full_validation_from(Some("0")));
    assert!(!force_full_validation_from(None));
    assert!(!force_full_validation_from(Some("true")));
    assert!(!force_full_validation_from(Some("")));
    assert!(!force_full_validation_from(Some("11")));
}

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
        acquisition: ApprovedArtifactAcquisition {
            artifact_id: runtime_id.into(),
            artifact_kind: AcquisitionArtifactKind::Runtime,
            source_type: AcquisitionSourceType::ApprovedHttps,
            primary_url: format!("https://example.test/{runtime_id}.zip"),
            allowed_redirect_hosts: vec!["example.test".into()],
            expected_filename: format!("{runtime_id}.zip"),
            expected_bytes: 7,
            expected_sha256: sha256_bytes(b"archive"),
            content_type: Some("application/octet-stream".into()),
            managed_relative_destination: managed_path.into(),
            public_distribution: false,
            installer_bundled: false,
            automatic_download: false,
            user_confirmation_required: true,
        },
        archive_format: "zip".into(),
        managed_relative_path: managed_path.into(),
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
            source_relative_path: LLAMA_CPP_LICENSE_SOURCE_PATH.into(),
            destination_relative_path: "LICENSE-MIT.txt".into(),
            bytes: LLAMA_CPP_LICENSE_BYTES.len() as u64,
            sha256: sha256_bytes(LLAMA_CPP_LICENSE_BYTES),
        },
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
        acquisition: ApprovedArtifactAcquisition {
            artifact_id: "test-model".into(),
            artifact_kind: AcquisitionArtifactKind::Model,
            source_type: AcquisitionSourceType::ApprovedHttps,
            primary_url: "https://example.test/test-model.gguf".into(),
            allowed_redirect_hosts: vec!["example.test".into()],
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

fn embedded_catalog_lf_bytes() -> Vec<u8> {
    let catalog = parse_catalog(CATALOG_BYTES).expect("parse embedded catalog fixture");
    canonical_bytes(&catalog)
}

fn with_crlf_line_endings(lf: &[u8]) -> Vec<u8> {
    let mut crlf = Vec::with_capacity(lf.len() + lf.iter().filter(|byte| **byte == b'\n').count());
    for byte in lf {
        if *byte == b'\n' {
            crlf.push(b'\r');
        }
        crlf.push(*byte);
    }
    crlf
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
    let license_bytes = source_controlled_runtime_license_bytes(&runtime.license_asset)
        .expect("test runtime license asset");
    fs::write(
        package.join(&runtime.license_asset.destination_relative_path),
        license_bytes,
    )
    .expect("write runtime license fixture");
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

fn custom_test_catalog() -> ApprovedArtifactCatalog {
    ApprovedArtifactCatalog {
        schema_version: SCHEMA_VERSION,
        catalog_id: CATALOG_ID.into(),
        catalog_version: "1.0.0-custom-test".into(),
        runtimes: vec![
            test_runtime(CUSTOM_MODEL_RUNTIME_ID, CUSTOM_MODEL_RUNTIME_ID),
            test_runtime(VULKAN_MODEL_RUNTIME_ID, VULKAN_MODEL_RUNTIME_ID),
        ],
        models: vec![test_model(vec![CUSTOM_MODEL_RUNTIME_ID.into()])],
    }
}

fn custom_test_source() -> ValidatedCustomModelSource {
    validate_custom_huggingface_url(
        "https://huggingface.co/localcomet/test-model/resolve/main/models/custom.gguf",
    )
    .expect("valid custom Hugging Face URL")
}

fn custom_test_artifact(bytes: &[u8]) -> CustomModelArtifact {
    custom_test_source().into_artifact(bytes.len() as u64, sha256_bytes(bytes))
}

fn install_custom_model(
    workspace: &TestWorkspace,
    model: &CustomModelArtifact,
    bytes: &[u8],
) -> PathBuf {
    let path = workspace
        .roots()
        .model_root
        .join(model.managed_relative_path.split('/').collect::<PathBuf>());
    fs::create_dir_all(path.parent().expect("custom model parent"))
        .expect("create custom model directory");
    fs::write(&path, bytes).expect("write custom model fixture");
    path
}

#[test]
fn custom_huggingface_url_is_canonical_stable_and_bounded() {
    let url = "https://huggingface.co/localcomet/test-model/resolve/main/models/custom.gguf";
    let source = validate_custom_huggingface_url(url).expect("canonical URL accepted");
    assert_eq!(
        source.model_id,
        format!("{CUSTOM_MODEL_ID_PREFIX}{}", sha256_bytes(url.as_bytes()))
    );
    assert_eq!(source.source_repository, "localcomet/test-model");
    assert_eq!(source.source_revision, "main");
    assert_eq!(source.asset_filename, "custom.gguf");
    assert_eq!(
        source.managed_relative_path,
        format!("custom/{}/custom.gguf", source.model_id)
    );
    assert_eq!(
        source.compatible_runtime_ids,
        vec![
            CUSTOM_MODEL_RUNTIME_ID.to_string(),
            VULKAN_MODEL_RUNTIME_ID.to_string()
        ]
    );

    for rejected in [
        "http://huggingface.co/owner/repo/resolve/main/model.gguf",
        "https://huggingface.co.evil.test/owner/repo/resolve/main/model.gguf",
        "https://evil.test/huggingface.co/owner/repo/resolve/main/model.gguf",
        "https://user@huggingface.co/owner/repo/resolve/main/model.gguf",
        "https://huggingface.co:443/owner/repo/resolve/main/model.gguf",
        "https://HUGGINGFACE.CO/owner/repo/resolve/main/model.gguf",
        "https://huggingface.co/owner/repo/blob/main/model.gguf",
        "https://huggingface.co/owner/repo/resolve/main/model.gguf?token=secret",
        "https://huggingface.co/owner/repo/resolve/main/model.gguf#fragment",
        "https://huggingface.co/owner/repo/resolve/main/../model.gguf",
        "https://huggingface.co/owner/repo/resolve/main/%2e%2e/model.gguf",
        "https://huggingface.co/owner/repo/resolve/main/model.bin",
        "https://huggingface.co/owner/repo/resolve/main/CON.gguf",
    ] {
        assert!(
            validate_custom_huggingface_url(rejected).is_err(),
            "must reject {rejected}"
        );
    }
}

#[test]
fn local_import_source_is_hash_bound_and_registers_as_a_valid_custom_model() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let asset_sha256 = sha256_bytes(TEST_MODEL_BYTES);
    let source_url = format!("local://import/{asset_sha256}/custom.gguf");
    let source = validate_local_import_source(&source_url, &asset_sha256)
        .expect("local source must be canonical");
    let model = source.into_artifact(TEST_MODEL_BYTES.len() as u64, asset_sha256.clone());

    install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("valid local import must register");

    assert_eq!(service.custom_models_snapshot(), vec![model]);
    assert!(
        validate_local_import_source("local://import/not-a-sha256/custom.gguf", &asset_sha256)
            .is_err()
    );
}

#[test]
fn custom_manifest_roundtrips_without_entering_approved_inventory() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let model = custom_test_artifact(TEST_MODEL_BYTES);
    install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("durably register validated custom model");

    let model_catalog = service.model_catalog();
    assert_eq!(model_catalog.models.len(), catalog.models.len());
    assert_eq!(model_catalog.custom_models.len(), 1);
    assert_eq!(
        model_catalog.custom_models[0].trust_kind,
        ModelTrustKind::UserSupplied
    );
    assert!(service.approved_download_artifact(&model.model_id).is_err());
    assert!(service.artifact_validation_status(&model.model_id).is_err());
    let installed = service.installed_artifacts();
    assert_eq!(
        installed.artifacts.len(),
        catalog.runtimes.len() + catalog.models.len()
    );
    assert_eq!(installed.custom_artifacts.len(), 1);
    assert_eq!(
        installed.custom_artifacts[0].installation_status,
        InstallationStatus::Valid
    );

    let bundle = service.artifact_trust_bundle();
    assert_eq!(bundle.model_catalog.custom_models.len(), 1);
    assert_eq!(bundle.installed_artifacts.custom_artifacts.len(), 1);
    assert_eq!(
        bundle.model_catalog.custom_models[0].model_id,
        bundle.installed_artifacts.custom_artifacts[0].artifact_id
    );
    assert_eq!(
        bundle.runtime_catalog.catalog_digest,
        bundle.model_catalog.catalog_digest
    );
    assert_eq!(
        bundle.model_catalog.catalog_digest,
        bundle.installed_artifacts.catalog_digest
    );

    drop(service);
    let reloaded = service_for(&catalog, &workspace);
    assert_eq!(reloaded.custom_model(&model.model_id).unwrap(), Some(model));
}

#[test]
fn legacy_single_cpu_custom_manifest_is_loaded_not_silently_dropped() {
    // Defect caught live (2026-08-15): manifests written before custom
    // imports recorded the Vulkan runtime were rejected wholesale by the
    // strict compatible_runtime_ids equality, silently dropping every
    // imported custom model at startup via unwrap_or_default.
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let model = custom_test_artifact(TEST_MODEL_BYTES);
    install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("durably register validated custom model");
    drop(service);

    // Rewrite the durable manifest into the legacy single-CPU shape.
    let manifest_path = workspace.roots().state_root.join(CUSTOM_MANIFEST_FILENAME);
    let mut manifest: Value =
        serde_json::from_str(&fs::read_to_string(&manifest_path).expect("read custom manifest"))
            .expect("parse custom manifest");
    manifest["models"][0]["compatible_runtime_ids"] = serde_json::json!([CUSTOM_MODEL_RUNTIME_ID]);
    fs::write(&manifest_path, serde_json::to_string(&manifest).unwrap())
        .expect("write legacy custom manifest");

    let reloaded = service_for(&catalog, &workspace);
    let loaded = reloaded
        .custom_model(&model.model_id)
        .expect("custom model lookup")
        .expect("legacy single-CPU custom model must load instead of being dropped");
    assert_eq!(
        loaded.compatible_runtime_ids,
        vec![CUSTOM_MODEL_RUNTIME_ID.to_string()]
    );

    // Any other runtime-list deviation still fails closed.
    let mut tampered = manifest.clone();
    tampered["models"][0]["compatible_runtime_ids"] = serde_json::json!([VULKAN_MODEL_RUNTIME_ID]);
    fs::write(&manifest_path, serde_json::to_string(&tampered).unwrap())
        .expect("write tampered custom manifest");
    let rejected = service_for(&catalog, &workspace);
    assert_eq!(rejected.custom_models_snapshot().len(), 0);
}

#[test]
fn malformed_oversize_and_legacy_custom_manifests_fail_closed() {
    for bytes in [
        b"{not-json".to_vec(),
        br#"{"schema_version":1,"models":[],"unexpected":true}"#.to_vec(),
        br#"{"schema_version":1,"schema_version":1,"models":[]}"#.to_vec(),
        vec![b' '; MAX_CUSTOM_MANIFEST_BYTES as usize + 1],
    ] {
        let workspace = TestWorkspace::new();
        let roots = workspace.roots();
        fs::create_dir_all(&roots.state_root).expect("create state root");
        fs::write(roots.state_root.join(CUSTOM_MANIFEST_FILENAME), bytes)
            .expect("write rejected custom manifest");
        let service = service_for(&custom_test_catalog(), &workspace);
        assert!(service.custom_models_snapshot().is_empty());
        assert_eq!(service.model_catalog().models.len(), 1);
    }

    let workspace = TestWorkspace::new();
    fs::write(
        workspace.root.join("custom_models.json"),
        serde_json::to_vec(&vec![test_model(vec![CUSTOM_MODEL_RUNTIME_ID.into()])])
            .expect("serialize legacy fixture"),
    )
    .expect("write legacy custom file");
    let service = service_for(&custom_test_catalog(), &workspace);
    assert!(service.custom_models_snapshot().is_empty());
}

#[test]
fn custom_registration_requires_full_validation_and_readiness_marks_trust() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let model = custom_test_artifact(TEST_MODEL_BYTES);
    let error = service
        .register_custom_model(model.clone())
        .expect_err("missing bytes cannot become durable nomination");
    assert_eq!(error.code(), "custom_model_not_valid");
    assert!(!workspace
        .roots()
        .state_root
        .join(CUSTOM_MANIFEST_FILENAME)
        .exists());

    install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
    let path = install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("validated custom model registers");
    let readiness = service
        .model_readiness(&model.model_id)
        .expect("custom readiness");
    assert_eq!(readiness.model_trust_kind, ModelTrustKind::UserSupplied);
    assert_eq!(readiness.readiness, ModelReadiness::Ready);
    assert!(readiness.launchable);

    let mut changed = TEST_MODEL_BYTES.to_vec();
    changed[5] ^= 1;
    fs::write(path, changed).expect("tamper custom model");
    assert_eq!(
        service
            .validate_custom_model_artifact(&model, true)
            .installation_status,
        InstallationStatus::HashMismatch
    );
}

#[test]
fn custom_remove_handles_missing_file_and_durably_unregisters() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let model = custom_test_artifact(TEST_MODEL_BYTES);
    let path = install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("register custom model");
    fs::remove_file(&path).expect("simulate missing custom model");
    assert!(!service
        .remove_custom_model_file_if_present(&model)
        .expect("missing custom model is removable"));
    service
        .unregister_custom_model(&model.model_id)
        .expect("durably unregister custom model");
    assert!(service.custom_models_snapshot().is_empty());
    drop(service);
    assert!(service_for(&catalog, &workspace)
        .custom_models_snapshot()
        .is_empty());
}

#[test]
fn runtime_start_approval_binds_custom_digest_only() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    assert_eq!(
        service
            .runtime_start_approval_input("test-model", None, None)
            .expect("approved input"),
        serde_json::json!({ "model_id": "test-model" })
    );
    assert!(service
        .runtime_start_approval_input("test-model", Some(&"0".repeat(64)), None)
        .is_err());

    let model = custom_test_artifact(TEST_MODEL_BYTES);
    install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("register custom model");
    assert!(service
        .runtime_start_approval_input(&model.model_id, None, None)
        .is_err());
    assert!(service
        .runtime_start_approval_input(&model.model_id, Some(&"0".repeat(64)), None)
        .is_err());
    assert_eq!(
        service
            .runtime_start_approval_input(&model.model_id, Some(&model.asset_sha256), None)
            .expect("digest-bound custom input"),
        serde_json::json!({
            "model_id": model.model_id,
            "custom_sha256": model.asset_sha256,
        })
    );
}

#[test]
fn runtime_start_approval_binds_explicit_runtime_id_into_digest() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let empty_runtime = service.runtime_start_approval_input("test-model", None, Some(""));
    assert_eq!(
        empty_runtime.expect("empty runtime id behaves as absent"),
        serde_json::json!({ "model_id": "test-model" })
    );
    let incompatible =
        service.runtime_start_approval_input("test-model", None, Some("unknown-runtime-id"));
    assert!(
        incompatible.is_err(),
        "an incompatible runtime id must fail closed before approval"
    );
    let compatible = catalog
        .runtimes
        .iter()
        .find(|runtime| {
            catalog
                .models
                .iter()
                .find(|model| model.model_id == "test-model")
                .map(|model| model.compatible_runtime_ids.contains(&runtime.runtime_id))
                .unwrap_or(false)
        })
        .expect("a compatible runtime exists");
    assert_eq!(
        service
            .runtime_start_approval_input("test-model", None, Some(&compatible.runtime_id))
            .expect("runtime-bound input"),
        serde_json::json!({
            "model_id": "test-model",
            "runtime_id": compatible.runtime_id,
        })
    );
}

#[test]
fn runtime_start_digest_matches_frontend_approval_input_for_all_compute_modes() {
    let workspace = TestWorkspace::new();
    let catalog = custom_test_catalog();
    let service = service_for(&catalog, &workspace);
    let model = custom_test_artifact(TEST_MODEL_BYTES);
    install_custom_model(&workspace, &model, TEST_MODEL_BYTES);
    service
        .register_custom_model(model.clone())
        .expect("register custom model");
    let supervisor = crate::managed_runtime::ManagedRuntimeSupervisor::new(Arc::new(service));
    let model_id = model.model_id.clone();
    let sha = model.asset_sha256.clone();

    // The canonical runtime.start approval input binds override keys only
    // when a concrete value exists. JSON.stringify drops `undefined` keys,
    // and a null override is semantically absent, so the frontend omits
    // both. Compute mode profiles resolve to:
    //   gpu    -> no override keys
    //   hybrid -> ctx_size_override=2048, gpu_layers_override=8
    //   cpu    -> ctx_size_override=2048, gpu_layers_override=0
    let frontend_forms = [
        serde_json::json!({
            "model_id": model_id,
            "custom_sha256": sha,
        }),
        serde_json::json!({
            "model_id": model_id,
            "custom_sha256": sha,
            "ctx_size_override": 2048,
            "gpu_layers_override": 8,
        }),
        serde_json::json!({
            "model_id": model_id,
            "custom_sha256": sha,
            "ctx_size_override": 2048,
            "gpu_layers_override": 0,
        }),
        serde_json::json!({
            "model_id": model_id,
            "custom_sha256": sha,
            "runtime_id": CUSTOM_MODEL_RUNTIME_ID,
        }),
        serde_json::json!({
            "model_id": model_id,
            "custom_sha256": sha,
            "runtime_id": VULKAN_MODEL_RUNTIME_ID,
            "ctx_size_override": 2048,
            "gpu_layers_override": 8,
        }),
        serde_json::json!({
            "model_id": model_id,
            "custom_sha256": sha,
            "runtime_id": VULKAN_MODEL_RUNTIME_ID,
            "ctx_size_override": 2048,
            "gpu_layers_override": 0,
        }),
    ];
    let rust_forms = [
        supervisor
            .runtime_start_approval_input_with_overrides(&model_id, Some(&sha), None, None, None)
            .expect("gpu without runtime"),
        supervisor
            .runtime_start_approval_input_with_overrides(
                &model_id,
                Some(&sha),
                None,
                Some(2048),
                Some(8),
            )
            .expect("hybrid without runtime"),
        supervisor
            .runtime_start_approval_input_with_overrides(
                &model_id,
                Some(&sha),
                None,
                Some(2048),
                Some(0),
            )
            .expect("cpu without runtime"),
        supervisor
            .runtime_start_approval_input_with_overrides(
                &model_id,
                Some(&sha),
                Some(CUSTOM_MODEL_RUNTIME_ID),
                None,
                None,
            )
            .expect("gpu with cpu runtime"),
        supervisor
            .runtime_start_approval_input_with_overrides(
                &model_id,
                Some(&sha),
                Some(VULKAN_MODEL_RUNTIME_ID),
                Some(2048),
                Some(8),
            )
            .expect("hybrid with vulkan runtime"),
        supervisor
            .runtime_start_approval_input_with_overrides(
                &model_id,
                Some(&sha),
                Some(VULKAN_MODEL_RUNTIME_ID),
                Some(2048),
                Some(0),
            )
            .expect("cpu with vulkan runtime"),
    ];

    for (frontend, rust_form) in frontend_forms.iter().zip(rust_forms.iter()) {
        assert_eq!(
            frontend, rust_form,
            "frontend approval input must byte-match the validated Rust input"
        );
        assert_eq!(
            crate::approval::canonical_input_digest(frontend),
            crate::approval::canonical_input_digest(rust_form),
            "issuance digest must equal validation digest"
        );
    }
}

#[test]
fn application_data_root_anchors_runtime_model_state_and_acquisition_paths() {
    let workspace = TestWorkspace::new();
    let application_root = workspace.root.join("isolated-profile").join("LocalComet");
    fs::create_dir_all(&application_root).expect("create isolated application root");
    let catalog = test_catalog();
    let service = ArtifactTrustService::from_catalog_bytes(
        &canonical_bytes(&catalog),
        ManagedArtifactRoots::from_application_data_root(&application_root),
    )
    .expect("create isolated trust service");
    let runtime = service
        .approved_download_artifact("test-runtime")
        .expect("approved runtime");
    let model = service
        .approved_download_artifact("test-model")
        .expect("approved model");

    assert_eq!(service.roots().app_data_root, application_root);
    assert_eq!(
        service.roots().runtime_root,
        service
            .roots()
            .app_data_root
            .join("runtimes")
            .join("llama.cpp")
    );
    assert_eq!(
        service.roots().model_root,
        service.roots().app_data_root.join("models")
    );
    assert_eq!(
        service.roots().state_root,
        service.roots().app_data_root.join("runtime-state")
    );
    assert_eq!(
        service.acquisition_root().expect("acquisition root"),
        service.roots().app_data_root.join("acquisition")
    );
    assert_eq!(
        service
            .acquisition_event_log_path()
            .expect("acquisition diagnostic log path"),
        service
            .roots()
            .app_data_root
            .join("logs")
            .join("acquisition-events.jsonl")
    );
    assert!(service
        .download_destination(&runtime)
        .expect("runtime destination")
        .starts_with(&service.roots().app_data_root));
    assert!(service
        .download_destination(&model)
        .expect("model destination")
        .starts_with(&service.roots().app_data_root));
}

#[test]
fn isolated_model_root_neither_discovers_nor_targets_a_default_profile_model() {
    let workspace = TestWorkspace::new();
    let default_root = workspace.root.join("default-profile").join("LocalComet");
    let isolated_root = workspace.root.join("isolated-profile").join("LocalComet");
    let catalog = test_catalog();
    let default_model = default_root
        .join("models")
        .join("test-model")
        .join("test-model.gguf");
    fs::create_dir_all(default_model.parent().expect("default model parent"))
        .expect("create default model parent");
    fs::write(&default_model, TEST_MODEL_BYTES).expect("write default model fixture");
    fs::create_dir_all(&isolated_root).expect("create isolated root");
    let service = ArtifactTrustService::from_catalog_bytes(
        &canonical_bytes(&catalog),
        ManagedArtifactRoots::from_application_data_root(&isolated_root),
    )
    .expect("create isolated trust service");
    let model = service
        .approved_download_artifact("test-model")
        .expect("approved model");
    let removal_destination = service
        .download_destination(&model)
        .expect("removal destination");

    assert_eq!(
        service
            .artifact_validation_status("test-model")
            .expect("model validation")
            .installation_status,
        InstallationStatus::NotInstalled
    );
    assert!(default_model.is_file());
    assert_eq!(
        removal_destination,
        isolated_root
            .join("models")
            .join("test-model")
            .join("test-model.gguf")
    );
    assert!(!removal_destination.starts_with(&default_root));
}

fn assert_catalog_invalid(catalog: &ApprovedArtifactCatalog) {
    assert!(validate_catalog(catalog).is_err());
}

// Manual re-canonicalization helper. It writes the catalog resource file
// back to disk, so it must never run as part of the automatic suite
// (cargo test gates run it otherwise). Invoke explicitly with
// `cargo test -- --ignored dump_canonical_catalog` when the pinned
// catalog bytes intentionally change.
#[ignore]
#[test]
fn dump_canonical_catalog() {
    let bytes = include_bytes!("../resources/localcomet/approved-artifacts.v1.json");
    let catalog: ApprovedArtifactCatalog = serde_json::from_slice(bytes).unwrap();
    let lf = canonical_bytes(&catalog);
    println!("LF HASH: {}", sha256_bytes(&lf));
    let mut canonical = serde_json::to_string_pretty(&catalog).unwrap();
    canonical.push('\n');
    std::fs::write("resources/localcomet/approved-artifacts.v1.json", canonical).unwrap();
}

#[test]
fn embedded_catalog_is_canonical_and_exactly_pinned() {
    let workspace = TestWorkspace::new();
    let catalog_bytes =
        canonical_embedded_catalog_bytes().expect("embedded catalog identity must be valid");
    let service =
        ArtifactTrustService::from_catalog_bytes(catalog_bytes.as_ref(), workspace.roots())
            .expect("embedded catalog must be valid");
    {
        let bundle = service.artifact_trust_bundle();
        eprintln!(
            "DIAG bundle: runtime_catalog.runtimes={} model_catalog.models={} custom={} installed_artifacts={} installed_custom={} digest={}",
            bundle.runtime_catalog.runtimes.len(),
            bundle.model_catalog.models.len(),
            bundle.model_catalog.custom_models.len(),
            bundle.installed_artifacts.artifacts.len(),
            bundle.installed_artifacts.custom_artifacts.len(),
            bundle.runtime_catalog.catalog_digest,
        );
        for m in &bundle.model_catalog.models {
            eprintln!(
                "DIAG model {} compatible={:?}",
                m.model_id, m.compatible_runtime_ids
            );
        }
        for r in &bundle.runtime_catalog.runtimes {
            eprintln!("DIAG runtime {} variant={}", r.runtime_id, r.variant);
        }
    }
    assert_eq!(
        sha256_bytes(catalog_bytes.as_ref()),
        EMBEDDED_CATALOG_SHA256
    );
    assert_eq!(service.catalog.runtimes.len(), 2);
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
    assert_eq!(runtime.archive_members.len(), 51);
    assert_eq!(
        runtime
            .archive_members
            .iter()
            .filter(|member| member.disposition == RuntimeArchiveMemberDisposition::Install)
            .count(),
        30
    );
    assert_eq!(runtime.required_files.len(), 30);

    let gpu_runtime = &service.catalog.runtimes[1];
    assert_eq!(
        gpu_runtime.runtime_id,
        "llama-cpp-windows-x86-64-vulkan-bootstrap"
    );
    assert_eq!(gpu_runtime.release_tag, "b10068");
    assert_eq!(gpu_runtime.variant, "vulkan");
    assert_eq!(gpu_runtime.asset_bytes, 33_271_704);
    assert_eq!(
        gpu_runtime.asset_sha256,
        "4f3e6fd215fdf22d2fd6232a5501f9e791a93d9193db4faf59e391eff90f6169"
    );
    assert_eq!(gpu_runtime.archive_members.len(), 52);
    assert_eq!(
        gpu_runtime
            .archive_members
            .iter()
            .filter(|member| member.disposition == RuntimeArchiveMemberDisposition::Install)
            .count(),
        31
    );
    assert_eq!(gpu_runtime.required_files.len(), 31);
    assert!(gpu_runtime
        .required_files
        .iter()
        .any(|file| file.relative_path == "ggml-vulkan.dll"));
    assert_eq!(
        runtime.license_asset.source_relative_path,
        "third_party/llama.cpp/LICENSE-MIT.txt"
    );
    assert_eq!(
        runtime.license_asset.destination_relative_path,
        "LICENSE-MIT.txt"
    );
    assert_eq!(runtime.license_asset.bytes, 1_078);
    assert_eq!(
        runtime.license_asset.sha256,
        "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d"
    );

    let model = &service.catalog.models[0];
    assert_eq!(model.model_id, "qwen2.5-7b-instruct-q4-k-m");
    assert_eq!(
        model.upstream_revision,
        "a8bb3906b78b3009770d7ae7d116be2ea892802d"
    );
    assert_eq!(model.asset_filename, "Qwen2.5-7B-Instruct-Q4_K_M.gguf");
    assert_eq!(model.asset_bytes, 4_683_073_952);
    assert_eq!(
        model.asset_sha256,
        "3e357ab3eda2c442f25c0080bb8998eedc05fd16ce1728eacff9ccc5c3d240c6"
    );
    assert_eq!(
        model.acquisition.primary_url,
        "https://huggingface.co/lmstudio-community/Qwen2.5-7B-Instruct-GGUF/resolve/a8bb3906b78b3009770d7ae7d116be2ea892802d/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    );
    assert_eq!(
        model.acquisition.expected_filename,
        "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    );
    assert_eq!(model.acquisition.expected_bytes, 4_683_073_952);
    assert_eq!(
        model.acquisition.expected_sha256,
        "3e357ab3eda2c442f25c0080bb8998eedc05fd16ce1728eacff9ccc5c3d240c6"
    );
    let model_hosts: Vec<&str> = model
        .acquisition
        .allowed_redirect_hosts
        .iter()
        .map(String::as_str)
        .collect();
    assert_eq!(
        model_hosts,
        vec![
            "cas-bridge.xethub.hf.co",
            "cdn-lfs-us-1.hf.co",
            "cdn-lfs.hf.co",
            "huggingface.co",
            "transfer.xethub.hf.co",
            "us.aws.cdn.hf.co",
        ]
    );
    assert!(!runtime
        .acquisition
        .allowed_redirect_hosts
        .iter()
        .any(|host| host == "us.aws.cdn.hf.co"));
}

#[test]
fn synthetic_lf_and_crlf_catalogs_normalize_to_the_same_pinned_bytes() {
    let workspace = TestWorkspace::new();
    let lf = embedded_catalog_lf_bytes();
    let normalized_lf =
        normalize_catalog_line_endings(&lf).expect("canonical LF must be accepted unchanged");
    assert!(matches!(normalized_lf, Cow::Borrowed(_)));
    assert_eq!(normalized_lf.as_ref(), lf.as_slice());
    let pinned_lf = canonical_catalog_bytes(&lf).expect("canonical LF must match the pin");
    ArtifactTrustService::from_catalog_bytes(pinned_lf.as_ref(), workspace.roots())
        .expect("LF catalog must retain schema and canonical validation");

    let crlf = with_crlf_line_endings(&lf);
    assert!(crlf.windows(2).any(|pair| pair == b"\r\n"));
    let normalized_crlf = normalize_catalog_line_endings(&crlf)
        .expect("synthetic CRLF must execute the normalization branch");
    assert!(matches!(normalized_crlf, Cow::Owned(_)));
    assert_eq!(normalized_crlf.as_ref(), lf.as_slice());
    let pinned_crlf =
        canonical_catalog_bytes(&crlf).expect("equivalent CRLF must match the LF pin");
    assert_eq!(sha256_bytes(pinned_crlf.as_ref()), EMBEDDED_CATALOG_SHA256);
    ArtifactTrustService::from_catalog_bytes(pinned_crlf.as_ref(), workspace.roots())
        .expect("normalized CRLF catalog must retain schema and canonical validation");
}

#[test]
fn catalog_line_endings_reject_bare_cr_and_mixed_invalid_input() {
    let lf = embedded_catalog_lf_bytes();
    let first_lf = lf
        .iter()
        .position(|byte| *byte == b'\n')
        .expect("catalog contains line endings");
    let mut bare_cr = lf.clone();
    bare_cr[first_lf] = b'\r';
    assert!(normalize_catalog_line_endings(&bare_cr).is_err());
    assert!(canonical_catalog_bytes(&bare_cr).is_err());

    let mut mixed = with_crlf_line_endings(&lf);
    let last_cr = mixed
        .iter()
        .rposition(|byte| *byte == b'\r')
        .expect("CRLF fixture contains CR");
    mixed.remove(last_cr + 1);
    assert!(mixed.windows(2).any(|pair| pair == b"\r\n"));
    assert!(mixed.contains(&b'\r'));
    assert!(normalize_catalog_line_endings(&mixed).is_err());
    assert!(canonical_catalog_bytes(&mixed).is_err());
}

#[test]
fn catalog_normalization_cannot_bypass_the_pinned_sha256() {
    let lf = embedded_catalog_lf_bytes();

    let mut one_byte_mutation = lf.clone();
    one_byte_mutation[0] ^= 1;
    assert!(canonical_catalog_bytes(&one_byte_mutation).is_err());

    let mut appended = lf.clone();
    appended.push(b' ');
    assert!(canonical_catalog_bytes(&appended).is_err());

    let mut removed = lf.clone();
    removed.pop();
    assert!(canonical_catalog_bytes(&removed).is_err());

    let mut whitespace_mutation = lf.clone();
    let first_lf = whitespace_mutation
        .iter()
        .position(|byte| *byte == b'\n')
        .expect("catalog contains line endings");
    whitespace_mutation.insert(first_lf, b' ');
    assert!(canonical_catalog_bytes(&whitespace_mutation).is_err());

    let unrelated_crlf = b"{\r\n  \"unrelated\": true\r\n}\r\n";
    let normalized = normalize_catalog_line_endings(unrelated_crlf)
        .expect("well-formed CRLF separators may be normalized");
    assert_eq!(normalized.as_ref(), b"{\n  \"unrelated\": true\n}\n");
    assert!(canonical_catalog_bytes(unrelated_crlf).is_err());
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
    catalog.models[0].provider = "   ".into();
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.models[0].display_name = "bad\nname".into();
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.models[0].asset_filename = "bad?.gguf".into();
    catalog.models[0].managed_relative_path = "test-model/bad?.gguf".into();
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
    catalog.runtimes[0].archive_members.pop();
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.runtimes[0]
        .archive_members
        .iter_mut()
        .find(|member| member.relative_path == "llama-server.exe")
        .expect("test launcher envelope member")
        .disposition = RuntimeArchiveMemberDisposition::RecognizedNotInstalled;
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.runtimes[0].license_asset.sha256 = "0".repeat(64);
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.models[0].public_distribution = true;
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.models[0].acquisition.primary_url = "http://example.test/model.gguf".into();
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.runtimes[0].acquisition.allowed_redirect_hosts =
        vec!["z.example.test".into(), "a.example.test".into()];
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.models[0].acquisition.expected_sha256 = "a".repeat(64);
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.runtimes[0].acquisition.managed_relative_destination = "../runtime".into();
    assert_catalog_invalid(&catalog);

    let mut catalog = baseline.clone();
    catalog.models[0].acquisition.automatic_download = true;
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
    let hostile_inventory = workspace
        .roots()
        .state_root
        .join("installed-artifacts.v1.json");
    for contents in [
        br#"{not-json"#.as_slice(),
        br#"{"schema_version":1,"catalog_digest":"stale","artifact_id":"unknown-runtime","relative_path":"../../outside","approved":true}"#.as_slice(),
        br#"{"schema_version":1,"catalog_digest":"stale","artifact_id":"unknown-runtime","relative_path":"C:/outside/runtime.exe","hash_bypass":true}"#.as_slice(),
    ] {
        fs::write(&hostile_inventory, contents).expect("write hostile inventory");
        assert!(service
            .artifact_validation_status("unknown-runtime")
            .is_err());
        assert_eq!(service.installed_artifacts().artifacts.len(), 2);
        assert!(service
            .model_readiness("test-model")
            .expect("readiness remains live-derived")
            .launchable);
    }
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
fn validation_cache_same_size_changed_mtime_rehashes_and_rejects_model() {
    let workspace = TestWorkspace::new();
    let catalog = test_catalog();
    let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
    let service = service_for(&catalog, &workspace);
    let first = service.validate_model(&catalog.models[0]);
    assert_eq!(first.outcome.status, InstallationStatus::Valid);
    assert_eq!(first.source, ValidationSource::Hashed);

    let original_modified = fs::metadata(&model_path)
        .expect("model metadata")
        .modified()
        .expect("model mtime");
    fs::write(&model_path, b"GGUFtest-mOdel").expect("same-size tamper");
    let file = OpenOptions::new()
        .write(true)
        .open(&model_path)
        .expect("open tampered model");
    file.set_times(
        fs::FileTimes::new().set_modified(original_modified + std::time::Duration::from_secs(2)),
    )
    .expect("set changed mtime");
    drop(file);

    let validation = service.validate_model(&catalog.models[0]);
    assert_eq!(validation.source, ValidationSource::Hashed);
    assert_eq!(validation.outcome.status, InstallationStatus::HashMismatch);
    assert_ne!(
        validation.outcome.observed_sha256.as_deref(),
        Some(catalog.models[0].asset_sha256.as_str())
    );
}

#[test]
fn validation_cache_same_size_restored_mtime_is_declared_trust_boundary() {
    let workspace = TestWorkspace::new();
    let catalog = test_catalog();
    let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
    let service = service_for(&catalog, &workspace);
    let first = service.validate_model(&catalog.models[0]);
    assert_eq!(first.source, ValidationSource::Hashed);
    let original_modified = fs::metadata(&model_path)
        .expect("model metadata")
        .modified()
        .expect("model mtime");

    fs::write(&model_path, b"GGUFtest-mOdel").expect("same-size tamper");
    let file = OpenOptions::new()
        .write(true)
        .open(&model_path)
        .expect("open tampered model");
    file.set_times(fs::FileTimes::new().set_modified(original_modified))
        .expect("restore prior mtime");
    drop(file);
    assert_eq!(
        fs::metadata(&model_path)
            .expect("tampered metadata")
            .modified()
            .expect("tampered mtime"),
        original_modified
    );
    assert_ne!(
        sha256_file(&model_path).expect("hash tampered bytes"),
        catalog.models[0].asset_sha256
    );

    let validation = service.validate_model(&catalog.models[0]);
    assert_eq!(validation.source, ValidationSource::Cached);
    assert_eq!(validation.outcome.status, InstallationStatus::Valid);
    assert_eq!(
        validation.outcome.observed_sha256.as_deref(),
        Some(catalog.models[0].asset_sha256.as_str())
    );
}

#[test]
fn force_full_validation_rehashes_a_valid_cache_entry() {
    let workspace = TestWorkspace::new();
    let catalog = test_catalog();
    install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
    let service = service_for(&catalog, &workspace);
    assert_eq!(
        service.validate_model(&catalog.models[0]).source,
        ValidationSource::Hashed
    );
    assert_eq!(
        service.validate_model(&catalog.models[0]).source,
        ValidationSource::Cached
    );

    let forced = service
        .validate_model_with_force(&catalog.models[0], force_full_validation_from(Some("1")));
    assert_eq!(forced.source, ValidationSource::Hashed);
    assert_eq!(forced.outcome.status, InstallationStatus::Valid);
}

#[test]
fn validation_cache_deleted_model_reports_not_installed() {
    let workspace = TestWorkspace::new();
    let catalog = test_catalog();
    let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
    let service = service_for(&catalog, &workspace);
    assert_eq!(
        service.validate_model(&catalog.models[0]).outcome.status,
        InstallationStatus::Valid
    );
    fs::remove_file(model_path).expect("remove cached model");

    assert_eq!(
        service
            .artifact_validation_status("test-model")
            .expect("model status")
            .installation_status,
        InstallationStatus::NotInstalled
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
    let package = runtime_path.parent().expect("runtime package");
    let model_parent = model_path.parent().expect("model parent");
    let moved_package = package.with_file_name("moved-runtime");
    let moved_model_parent = model_parent.with_file_name("moved-model");

    assert!(OpenOptions::new().write(true).open(&model_path).is_err());
    assert!(OpenOptions::new().write(true).open(&runtime_path).is_err());
    assert!(fs::rename(package, &moved_package).is_err());
    assert!(fs::rename(model_parent, &moved_model_parent).is_err());
    drop(launch);
    assert!(OpenOptions::new().write(true).open(&model_path).is_ok());
    assert!(OpenOptions::new().write(true).open(&runtime_path).is_ok());
    fs::rename(package, &moved_package).expect("rename unlocked runtime directory");
    fs::rename(&moved_package, package).expect("restore runtime directory");
    fs::rename(model_parent, &moved_model_parent).expect("rename unlocked model directory");
    fs::rename(&moved_model_parent, model_parent).expect("restore model directory");

    let state_handles = service
        .guard_runtime_state_root()
        .expect("guard runtime state root");
    let state_root = workspace.roots().state_root;
    let moved_state = state_root.with_file_name("moved-state");
    assert!(fs::rename(&state_root, &moved_state).is_err());
    drop(state_handles);
    fs::rename(&state_root, &moved_state).expect("rename unlocked state directory");
    fs::rename(&moved_state, &state_root).expect("restore state directory");
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

#[test]
#[ignore = "requires the owner-provisioned UP05-WP00 bootstrap artifacts"]
fn provisioned_bootstrap_is_discovered_only_through_the_catalog() {
    let local_data = std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA is required");
    let application_data_root = Path::new(&local_data).join("LocalComet");
    let service = ArtifactTrustService::production(&application_data_root)
        .expect("embedded production catalog");
    assert_eq!(
        service.catalog.runtimes[0].runtime_id,
        "llama-cpp-windows-x86-64-cpu-bootstrap"
    );
    assert_eq!(
        service.catalog.models[0].model_id,
        "qwen2.5-7b-instruct-q4-k-m"
    );

    let installed = service.installed_artifacts();
    assert_eq!(installed.artifacts.len(), 2);
    assert!(installed
        .artifacts
        .iter()
        .all(|artifact| artifact.installation_status == InstallationStatus::Valid));
    let readiness = service
        .model_readiness("qwen2.5-7b-instruct-q4-k-m")
        .expect("approved model readiness");
    assert_eq!(readiness.compatibility, CompatibilityStatus::Compatible);
    assert_eq!(readiness.readiness, ModelReadiness::Ready);
    assert!(readiness.launchable);
    let launch = service
        .resolve_launch("qwen2.5-7b-instruct-q4-k-m")
        .expect("catalog-resolved launch identity");
    assert_eq!(launch.runtime_id, "llama-cpp-windows-x86-64-cpu-bootstrap");
    assert_eq!(launch.model_id, "qwen2.5-7b-instruct-q4-k-m");
    drop(launch);
    assert!(service
        .artifact_validation_status("unapproved-runtime")
        .is_err());
}

#[test]
#[ignore = "requires the owner-provisioned UP05-WP00 bootstrap artifacts to be temporarily moved"]
fn production_bootstrap_absence_is_live_derived() {
    let local_data = std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA is required");
    let application_data_root = Path::new(&local_data).join("LocalComet");
    let service = ArtifactTrustService::production(&application_data_root)
        .expect("embedded production catalog");
    let installed = service.installed_artifacts();
    assert_eq!(installed.artifacts.len(), 2);
    assert!(installed.artifacts.iter().all(|artifact| {
        artifact.installation_status == InstallationStatus::NotInstalled
            && artifact.observed_bytes.is_none()
            && artifact.observed_sha256.is_none()
    }));
    let readiness = service
        .model_readiness("qwen2.5-7b-instruct-q4-k-m")
        .expect("approved model readiness");
    assert_eq!(readiness.readiness, ModelReadiness::ModelNotInstalled);
    assert!(!readiness.launchable);
    assert!(service
        .resolve_launch("qwen2.5-7b-instruct-q4-k-m")
        .is_err());
    assert!(service
        .artifact_validation_status("unapproved-runtime")
        .is_err());
}
