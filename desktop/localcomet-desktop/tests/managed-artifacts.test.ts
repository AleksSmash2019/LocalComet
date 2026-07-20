import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ManagedRuntimePanel from '../src/lib/components/model/ManagedRuntimePanel.svelte';
import * as modelGatewayBridge from '../src/lib/bridge/modelGateway';
import {
  getManagedArtifactValidationStatus,
  getManagedInstalledArtifacts,
  getManagedModelCatalog,
  getManagedModelReadiness,
  getManagedRuntimeCatalog
} from '../src/lib/bridge/modelGateway';
import {
  managedRuntimeStore,
  modelGatewayStore,
  refreshManagedRuntimeStatus,
  resetModelGatewayStore,
  setManagedSelectedModel,
  startSelectedManagedRuntime
} from '../src/lib/stores/modelGateway';
import type { ArtifactInstallationStatus } from '../src/lib/types/modelGateway';

const RUNTIME_ID = 'llama-cpp-windows-x86-64-cpu-bootstrap';
const MODEL_ID = 'qwen2.5-1.5b-instruct-q4-k-m';
const CATALOG_DIGEST = 'a'.repeat(64);
const RUNTIME_SHA256 = 'b'.repeat(64);
const MODEL_SHA256 = 'c'.repeat(64);
const RUNTIME_BYTES = 1_000_000;
const MODEL_BYTES = 2_000_000;

let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let responses: Record<string, unknown> = {};

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    invokeCalls.push({ command, args });
    return responses[command] ?? {};
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (): Promise<() => void> => () => undefined)
}));

function catalogIdentity(digest = CATALOG_DIGEST) {
  return {
    schema_version: 1,
    catalog_id: 'localcomet-approved-artifacts',
    catalog_version: '1.0.0',
    catalog_digest: digest
  };
}

function runtimeFixture() {
  return {
    runtime_id: RUNTIME_ID,
    provider: 'ggml-org',
    release_tag: 'b6000',
    platform: 'windows',
    architecture: 'x86-64',
    variant: 'cpu',
    upstream_repository: 'https://github.com/ggml-org/llama.cpp',
    upstream_revision: 'b6000',
    asset_filename: 'llama-b6000-bin-win-cpu-x64.zip',
    asset_bytes: RUNTIME_BYTES,
    asset_sha256: RUNTIME_SHA256,
    archive_format: 'zip',
    permitted_bind_scope: 'loopback-only',
    supported_api_protocol: 'openai-compatible-v1',
    license_id: 'MIT',
    public_distribution: false,
    status: 'approved_internal_bootstrap'
  };
}

function modelFixture() {
  return {
    model_id: MODEL_ID,
    provider: 'Qwen',
    family: 'Qwen2.5',
    display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
    format: 'GGUF',
    quantization: 'Q4_K_M',
    upstream_repository: 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF',
    upstream_revision: 'main',
    asset_filename: 'qwen2.5-1.5b-instruct-q4_k_m.gguf',
    asset_bytes: MODEL_BYTES,
    asset_sha256: MODEL_SHA256,
    license_id: 'apache-2.0',
    compatible_runtime_ids: [RUNTIME_ID],
    public_distribution: false,
    installer_bundled: false,
    bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION',
    status: 'approved_internal_bootstrap'
  };
}

function runtimeCatalogFixture(digest = CATALOG_DIGEST) {
  return { ...catalogIdentity(digest), runtimes: [runtimeFixture()] };
}

function modelCatalogFixture(digest = CATALOG_DIGEST) {
  return {
    ...catalogIdentity(digest),
    engine: 'llama.cpp',
    model_root: '<MANAGED_MODEL_ROOT>',
    models: [modelFixture()],
    maximum_models: 32
  };
}

function validationFixture(
  artifactId: string,
  kind: 'runtime' | 'model',
  status: ArtifactInstallationStatus = 'valid'
) {
  const expectedBytes = kind === 'runtime' ? RUNTIME_BYTES : MODEL_BYTES;
  const expectedSha256 = kind === 'runtime' ? RUNTIME_SHA256 : MODEL_SHA256;
  return {
    ...catalogIdentity(),
    artifact_id: artifactId,
    kind,
    catalog_status: 'approved_internal_bootstrap',
    installation_status: status,
    expected_bytes: expectedBytes,
    expected_sha256: expectedSha256,
    observed_bytes: status === 'not_installed' || (kind === 'runtime' && status === 'valid') ? null : expectedBytes,
    observed_sha256: status === 'not_installed' || (kind === 'runtime' && status === 'valid') ? null : expectedSha256,
    validation_code: status,
    verified_unix_ms: 1_750_000_000_000
  };
}

function installedArtifactsFixture() {
  return {
    ...catalogIdentity(),
    artifacts: [
      validationFixture(RUNTIME_ID, 'runtime'),
      validationFixture(MODEL_ID, 'model')
    ]
  };
}

function readinessFixture(patch: Record<string, unknown> = {}) {
  return {
    ...catalogIdentity(),
    model_id: MODEL_ID,
    model_status: 'valid',
    compatible_runtime_ids: [RUNTIME_ID],
    selected_runtime_id: RUNTIME_ID,
    runtime_status: 'valid',
    compatibility: 'compatible',
    readiness: 'ready',
    launchable: true,
    ...patch
  };
}

function runtimeStatusFixture() {
  return {
    engine: 'llama.cpp',
    state: 'Stopped',
    installation: 'Installed',
    runtime_version: 'b6000',
    runtime_instance_id: null,
    runtime_instance_fingerprint: null,
    model_id: null,
    model_display_name: null,
    binding_fingerprint: null,
    model_state: 'Unavailable',
    inference_ready: false,
    last_error: null
  };
}

function installResponses(): void {
  invokeCalls = [];
  responses = {
    managed_runtime_status: runtimeStatusFixture(),
    managed_runtime_catalog: runtimeCatalogFixture(),
    managed_model_catalog: modelCatalogFixture(),
    managed_installed_artifacts: installedArtifactsFixture(),
    managed_artifact_validation_status: validationFixture(MODEL_ID, 'model'),
    managed_model_readiness: readinessFixture(),
    managed_runtime_logs: { stdout_tail: [], stderr_tail: [] },
    managed_runtime_start: {
      state: 'Ready',
      model_state: 'Ready',
      inference_ready: true,
      provider_id: 'managed-llama-cpp',
      model_id: MODEL_ID,
      model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      runtime_instance_id: 'd'.repeat(32),
      runtime_instance_fingerprint: 'e'.repeat(64)
    }
  };
}

describe('managed artifact trust frontend contract', () => {
  beforeEach(() => {
    resetModelGatewayStore();
    installResponses();
  });

  it('uses only the fixed read-only trust commands and stable artifact IDs', async () => {
    const runtimeCatalog = await getManagedRuntimeCatalog();
    const modelCatalog = await getManagedModelCatalog();
    await getManagedInstalledArtifacts();
    await getManagedArtifactValidationStatus(MODEL_ID);
    await getManagedModelReadiness(MODEL_ID);

    expect(invokeCalls).toEqual([
      { command: 'managed_runtime_catalog', args: undefined },
      { command: 'managed_model_catalog', args: undefined },
      { command: 'managed_installed_artifacts', args: undefined },
      { command: 'managed_artifact_validation_status', args: { artifactId: MODEL_ID } },
      { command: 'managed_model_readiness', args: { modelId: MODEL_ID } }
    ]);
    expect(runtimeCatalog.runtimes[0]).not.toHaveProperty('installation_status');
    expect(modelCatalog.models[0]).not.toHaveProperty('installation_status');
    expect(Object.keys(modelGatewayBridge)).not.toEqual(expect.arrayContaining([
      'approveManagedArtifact',
      'writeManagedCatalog',
      'loadManagedCatalog'
    ]));
  });

  it('keeps pure approval-list calls separate from live installed validation', async () => {
    await getManagedRuntimeCatalog();
    await getManagedModelCatalog();

    expect(invokeCalls.map((call) => call.command)).toEqual([
      'managed_runtime_catalog',
      'managed_model_catalog'
    ]);
  });

  it('preserves a confirmed harness binding when the runtime attach fingerprint is distinct', async () => {
    const runtimeInstanceId = 'd'.repeat(32);
    const attachFingerprint = 'e'.repeat(64);
    const boundFingerprint = 'f'.repeat(64);
    const binding = {
      provider_id: 'managed-llama-cpp' as const,
      harness_id: 'minimal' as const,
      model_id: MODEL_ID,
      binding_fingerprint: boundFingerprint,
      discovered_fingerprint: '9'.repeat(64),
      persistence: false as const,
      runtime_instance_id: runtimeInstanceId
    };
    managedRuntimeStore.update((state) => ({
      ...state,
      selectedModelId: MODEL_ID,
      harnessId: 'minimal',
      binding
    }));
    modelGatewayStore.update((state) => ({ ...state, binding, status: 'Bound' }));
    responses.managed_runtime_status = {
      ...runtimeStatusFixture(),
      state: 'Ready',
      model_state: 'Ready',
      inference_ready: true,
      runtime_instance_id: runtimeInstanceId,
      runtime_instance_fingerprint: '8'.repeat(64),
      model_id: MODEL_ID,
      model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      binding_fingerprint: attachFingerprint
    };

    await refreshManagedRuntimeStatus();

    expect(get(managedRuntimeStore).binding?.binding_fingerprint).toBe(boundFingerprint);
    expect(get(managedRuntimeStore).status?.binding_fingerprint).toBe(attachFingerprint);
    expect(get(modelGatewayStore).binding?.binding_fingerprint).toBe(boundFingerprint);
  });

  it('rejects path-like or non-canonical artifact IDs before invoking Tauri', async () => {
    for (const artifactId of ['../model', 'C:\\model', 'UPPERCASE', 'ab', 'model/child']) {
      await expect(getManagedArtifactValidationStatus(artifactId)).rejects.toMatchObject({ code: 'invalid_payload' });
      await expect(getManagedModelReadiness(artifactId)).rejects.toMatchObject({ code: 'invalid_payload' });
    }
    expect(invokeCalls).toHaveLength(0);
  });

  it('strictly rejects malformed, duplicate, or path-bearing catalog metadata', async () => {
    responses.managed_runtime_catalog = { ...runtimeCatalogFixture(), catalog_digest: CATALOG_DIGEST.toUpperCase() };
    await expect(getManagedRuntimeCatalog()).rejects.toMatchObject({ code: 'invalid_payload' });

    responses.managed_runtime_catalog = {
      ...runtimeCatalogFixture(),
      runtimes: [runtimeFixture(), runtimeFixture()]
    };
    await expect(getManagedRuntimeCatalog()).rejects.toMatchObject({ code: 'invalid_payload' });

    responses.managed_runtime_catalog = {
      ...runtimeCatalogFixture(),
      runtimes: [{ ...runtimeFixture(), absolute_path: 'C:\\untrusted\\runtime.exe' }]
    };
    await expect(getManagedRuntimeCatalog()).rejects.toMatchObject({ code: 'invalid_payload' });

    responses.managed_runtime_catalog = {
      ...runtimeCatalogFixture(),
      runtimes: [{ ...runtimeFixture(), installation_status: 'valid' }]
    };
    await expect(getManagedRuntimeCatalog()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('reconciles approved catalogs, installed validation, and readiness in the store', async () => {
    await refreshManagedRuntimeStatus();
    await setManagedSelectedModel(MODEL_ID);
    const state = get(managedRuntimeStore);

    expect(state.catalogIdentity?.catalog_digest).toBe(CATALOG_DIGEST);
    expect(state.runtimeCatalog.map((runtime) => runtime.runtime_id)).toEqual([RUNTIME_ID]);
    expect(state.catalog.map((model) => model.model_id)).toEqual([MODEL_ID]);
    expect(state.installedArtifacts.every((artifact) => artifact.installation_status === 'valid')).toBe(true);
    expect(state.installedArtifacts.find((artifact) => artifact.kind === 'runtime')).toMatchObject({
      observed_bytes: null,
      observed_sha256: null,
      validation_code: 'valid'
    });
    expect(state.readiness).toMatchObject({ model_id: MODEL_ID, readiness: 'ready', launchable: true });
    expect(state.lastError).toBeNull();

    const body = render(ManagedRuntimePanel).body;
    expect(body).toContain('Qwen2.5 1.5B Instruct Q4_K_M');
    expect(body).toContain('Start Runtime');
    expect(body).toContain('Stop Runtime');
    expect(body).toContain('Confirm Binding');
    expect(body).not.toMatch(/C:\\|absolute_path|Model path|Executable|Approve artifact|Download model/i);
  });

  it('keeps approval visible but derives non-installed UI state only from inventory and readiness', async () => {
    responses.managed_installed_artifacts = {
      ...catalogIdentity(),
      artifacts: [
        validationFixture(RUNTIME_ID, 'runtime'),
        validationFixture(MODEL_ID, 'model', 'not_installed')
      ]
    };
    responses.managed_model_readiness = readinessFixture({
      model_status: 'not_installed',
      compatibility: 'compatible',
      readiness: 'model_not_installed',
      launchable: false
    });

    await refreshManagedRuntimeStatus();
    await setManagedSelectedModel(MODEL_ID);
    const state = get(managedRuntimeStore);

    expect(state.catalog.map((model) => model.model_id)).toEqual([MODEL_ID]);
    expect(state.installedArtifacts.find((artifact) => artifact.artifact_id === MODEL_ID)?.installation_status).toBe('not_installed');
    expect(state.readiness).toMatchObject({ model_status: 'not_installed', launchable: false });
    expect(state.binding).toBeNull();
    expect(render(ManagedRuntimePanel).body).toMatch(/<button[^>]*disabled[^>]*>Start Runtime<\/button>/);
  });

  it('fails closed when catalog digests or inventory references disagree', async () => {
    responses.managed_model_catalog = modelCatalogFixture('f'.repeat(64));
    await refreshManagedRuntimeStatus();
    expect(get(managedRuntimeStore)).toMatchObject({
      catalogIdentity: null,
      runtimeCatalog: [],
      catalog: [],
      installedArtifacts: [],
      selectedModelId: '',
      binding: null,
      lastError: { code: 'invalid_payload' }
    });

    installResponses();
    responses.managed_installed_artifacts = {
      ...catalogIdentity(),
      artifacts: [
        validationFixture(RUNTIME_ID, 'runtime'),
        validationFixture('unknown-approved-model', 'model')
      ]
    };
    await refreshManagedRuntimeStatus();
    expect(get(managedRuntimeStore).catalog).toEqual([]);
    expect(get(managedRuntimeStore).lastError?.code).toBe('invalid_payload');
  });

  it('rechecks readiness before start and never launches a non-ready model', async () => {
    await refreshManagedRuntimeStatus();
    await setManagedSelectedModel(MODEL_ID);
    responses.managed_model_readiness = readinessFixture({
      model_status: 'not_installed',
      compatibility: 'compatible',
      readiness: 'model_not_installed',
      launchable: false
    });
    invokeCalls = [];

    await startSelectedManagedRuntime();

    expect(invokeCalls.map((call) => call.command)).toEqual(['managed_model_readiness']);
    expect(get(managedRuntimeStore).readiness?.launchable).toBe(false);
    expect(get(managedRuntimeStore).lastError?.code).toBe('model_not_ready');
  });

  it('rejects false launchable and inconsistent compatibility claims', async () => {
    responses.managed_model_readiness = readinessFixture({
      selected_runtime_id: null,
      runtime_status: 'not_installed',
      compatibility: 'no_compatible_runtime_installed'
    });
    await expect(getManagedModelReadiness(MODEL_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    responses.managed_model_readiness = readinessFixture({
      selected_runtime_id: null,
      runtime_status: 'not_installed',
      compatibility: 'incompatible_runtime_installed',
      readiness: 'incompatible',
      launchable: false
    });
    await expect(getManagedModelReadiness(MODEL_ID)).resolves.toMatchObject({
      compatibility: 'incompatible_runtime_installed',
      readiness: 'incompatible',
      launchable: false
    });
  });
});
