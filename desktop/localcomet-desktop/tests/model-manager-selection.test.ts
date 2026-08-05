import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import { afterEach, beforeAll } from 'vitest';
import { get } from 'svelte/store';
import ModelManagerSection from '../src/lib/components/model/ModelManagerSection.svelte';
import {
  artifactAcquisitionStore,
  initializeArtifactAcquisition,
  setUpManagedModel,
  downloadAndSetupManagedModel
} from '../src/lib/stores/artifactAcquisition';
import {
  connectSelectedManagedModel,
  managedRuntimeStore,
  refreshManagedRuntimeStatus,
  setManagedSelectedModel,
  stopSelectedManagedRuntime
} from '../src/lib/stores/modelGateway';
import type { ApprovedDownloadableArtifact, CustomDownloadableArtifact } from '../src/lib/types/modelGateway';

function makeModelArtifact(overrides: Partial<ApprovedDownloadableArtifact> = {}): ApprovedDownloadableArtifact {
  return {
    artifact_id: 'model-qwen1.5b',
    kind: 'model',
    trust_kind: 'approved_catalog',
    display_name: 'Qwen2.5-1.5B',
    expected_bytes: 1024,
    format: 'GGUF',
    quantization: 'Q4_K_M',
    license_id: 'Apache-2.0',
    source_identity: 'approved',
    user_confirmation_required: true,
    automatic_download: false,
    ...overrides
  };
}

function makeCustomModelArtifact(): CustomDownloadableArtifact {
  return {
    artifact_id: 'custom-owner-repo-model-1234567890ab',
    kind: 'model',
    trust_kind: 'user_supplied',
    display_name: 'Custom model',
    expected_bytes: 4096,
    expected_sha256: 'e'.repeat(64),
    format: 'GGUF',
    quantization: null,
    license_id: null,
    source_identity: 'https://huggingface.co/owner/repo/resolve/main/model.gguf',
    user_confirmation_required: true,
    automatic_download: false
  };
}

describe('ModelManagerSection multi-model selection', () => {
  afterEach(() => {
    artifactAcquisitionStore.set({
      artifacts: [],
      downloads: {},
      setup: { lifecycle: 'idle', artifact_id: null },
      lastError: null
    });
    managedRuntimeStore.set({
      selectedModelId: '',
      status: { state: 'NotInstalled' },
      catalog: [],
      runtimeCatalog: [],
      installedArtifacts: [],
      lastError: null,
      logs: { stdout_tail: [], stderr_tail: [] },
      readiness: null,
      catalogIdentity: null,
      harnessId: 'minimal',
      binding: null
    } as any);
  });

  it('exposes model-specific setup helpers in the artifact acquisition store', async () => {
    const { setUpManagedModel, downloadAndSetupManagedModel } = await import('../src/lib/stores/artifactAcquisition');
    expect(typeof setUpManagedModel).toBe('function');
    expect(typeof downloadAndSetupManagedModel).toBe('function');
  });

  it('renders a model select when multiple approved models are available', async () => {
    const runtimeArtifact: ApprovedDownloadableArtifact = {
      artifact_id: 'runtime-llama',
      kind: 'runtime',
      trust_kind: 'approved_catalog',
      display_name: 'llama.cpp',
      expected_bytes: 2048,
      format: 'runtime',
      quantization: '',
      license_id: 'MIT',
      source_identity: 'approved',
      user_confirmation_required: true,
      automatic_download: false
    };
    artifactAcquisitionStore.set({
      artifacts: [runtimeArtifact, makeModelArtifact({ artifact_id: 'model-a', display_name: 'Model A' }), makeModelArtifact({ artifact_id: 'model-b', display_name: 'Model B' })],
      downloads: {},
      setup: { lifecycle: 'idle', artifact_id: null },
      lastError: null
    });
    managedRuntimeStore.set({
      selectedModelId: 'model-a',
      status: { state: 'NotInstalled' },
      catalog: [],
      runtimeCatalog: [],
      installedArtifacts: [],
      lastError: null,
      logs: { stdout_tail: [], stderr_tail: [] },
      readiness: null,
      catalogIdentity: null,
      harnessId: 'minimal',
      binding: null
    } as any);

    const html = render(ModelManagerSection).body;
    expect(html).toContain('Model A');
    expect(html).toContain('Model B');
    expect(html).toContain('<select');
  });

  it('updates managed selected model via real store API', async () => {
    managedRuntimeStore.set({
      selectedModelId: '',
      status: { state: 'NotInstalled' },
      catalog: [],
      runtimeCatalog: [],
      installedArtifacts: [],
      lastError: null,
      logs: { stdout_tail: [], stderr_tail: [] },
      readiness: null,
      catalogIdentity: null,
      harnessId: 'minimal',
      binding: null
    } as any);

    await setManagedSelectedModel('model-a');
    expect(get(managedRuntimeStore).selectedModelId).toBe('model-a');
  });

  it('shows custom models separately with warning and invalid-removal guidance', () => {
    const customArtifact = makeCustomModelArtifact();
    artifactAcquisitionStore.set({
      artifacts: [makeModelArtifact(), customArtifact],
      downloads: {},
      setup: { lifecycle: 'idle', artifact_id: null },
      lastError: null
    });
    managedRuntimeStore.set({
      selectedModelId: customArtifact.artifact_id,
      status: { state: 'Stopped' },
      catalog: [],
      runtimeCatalog: [],
      installedArtifacts: [{
        artifact_id: customArtifact.artifact_id,
        kind: 'model',
        trust_kind: 'user_supplied',
        installation_status: 'hash_mismatch',
        expected_bytes: customArtifact.expected_bytes,
        expected_sha256: customArtifact.expected_sha256,
        observed_bytes: customArtifact.expected_bytes,
        observed_sha256: 'f'.repeat(64),
        validation_code: 'hash_mismatch',
        verified_unix_ms: 1
      }],
      lastError: null,
      logs: { stdout_tail: [], stderr_tail: [] },
      readiness: null,
      catalogIdentity: null,
      harnessId: 'minimal',
      binding: null
    } as any);

    const html = render(ModelManagerSection, { props: { mode: 'huggingface' } }).body;
    expect(html).toContain('Скачанные модели');
    expect(html).toContain('Внимание: модели скачиваются без гарантий');
    expect(html).toContain(customArtifact.source_identity);
    expect(html).toContain(customArtifact.expected_sha256);
    expect(html).toContain('Пользовательская модель не прошла проверку');
    expect(html).toMatch(/<button[^>]*class="danger[^"]*"[^>]*>Удалить модель<\/button>/);
    expect(html).not.toContain('2 записей');
  });

  it('displays empty state placeholder when selectedModelId is empty', () => {
    artifactAcquisitionStore.set({
      artifacts: [makeModelArtifact({ artifact_id: 'model-a', display_name: 'Model A' }), makeModelArtifact({ artifact_id: 'model-b', display_name: 'Model B' })],
      downloads: {},
      setup: { lifecycle: 'idle', artifact_id: null },
      lastError: null
    });
    managedRuntimeStore.set({
      selectedModelId: '',
      status: { state: 'NotInstalled' },
      catalog: [],
      runtimeCatalog: [],
      installedArtifacts: [],
      lastError: null,
      logs: { stdout_tail: [], stderr_tail: [] },
      readiness: null,
      catalogIdentity: null,
      harnessId: 'minimal',
      binding: null
    } as any);

    const html = render(ModelManagerSection).body;
    // When no model is selected, the first option should be the disabled "not_available" option
    expect(html).toContain('<option value="" disabled="" hidden="" selected="">');
    expect(html).toContain('Model A');
    expect(html).toContain('Model B');
    // Ensure the default auto-selection logic is absent
    expect(get(managedRuntimeStore).selectedModelId).toBe('');
  });
});
