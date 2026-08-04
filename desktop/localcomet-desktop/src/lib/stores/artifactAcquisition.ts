import { derived, get, writable } from 'svelte/store';
import {
  cancelArtifactDownload,
  getArtifactDownloadState,
  listApprovedDownloadableArtifacts,
  normalizeGatewayError,
  removeManagedModel,
  startApprovedArtifactDownload
} from '$lib/bridge/modelGateway';
import {
  connectSelectedManagedModel,
  managedRuntimeStore,
  refreshManagedRuntimeStatus,
  setManagedSelectedModel
} from '$lib/stores/modelGateway';
import type {
  ApprovedDownloadableArtifact,
  ArtifactDownloadState,
  SanitizedGatewayError
} from '$lib/types/modelGateway';

const DOWNLOAD_POLL_MS = 500;

export interface ArtifactAcquisitionPanelState {
  readonly artifacts: readonly ApprovedDownloadableArtifact[];
  readonly downloads: Readonly<Record<string, ArtifactDownloadState>>;
  readonly setup: {
    readonly lifecycle: 'idle' | 'running' | 'completed' | 'cancelled' | 'failed';
    readonly artifact_id: string | null;
  };
  readonly lastError: SanitizedGatewayError | null;
}

const initialState: ArtifactAcquisitionPanelState = {
  artifacts: [],
  downloads: {},
  setup: { lifecycle: 'idle', artifact_id: null },
  lastError: null
};

let lifecycleGeneration = 0;
let initialization: Promise<void> | null = null;

export const artifactAcquisitionStore = writable<ArtifactAcquisitionPanelState>(initialState);
export const acquisitionBusy = derived(artifactAcquisitionStore, (state) =>
  Object.values(state.downloads).some((download) => !isTerminal(download)) || state.setup.lifecycle === 'running'
);

export async function initializeArtifactAcquisition(): Promise<void> {
  if (initialization) return initialization;
  const generation = lifecycleGeneration;
  const pending = (async () => {
    try {
      const artifacts = await listApprovedDownloadableArtifacts();
      if (generation !== lifecycleGeneration) return;
      artifactAcquisitionStore.update((state) => ({ ...state, artifacts, lastError: null }));
    } catch (error) {
      if (generation !== lifecycleGeneration) return;
      artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
    }
  })();
  initialization = pending;
  try {
    await pending;
  } finally {
    if (initialization === pending) initialization = null;
  }
}

export async function downloadApprovedArtifact(artifactId: string): Promise<ArtifactDownloadState | null> {
  const artifact = get(artifactAcquisitionStore).artifacts.find((candidate) => candidate.artifact_id === artifactId);
  if (!artifact) return null;
  try {
    const started = await startApprovedArtifactDownload(artifact.artifact_id);
    recordDownload(started);
    return await followDownload(started);
  } catch (error) {
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
    return null;
  }
}

export async function cancelApprovedArtifactDownload(artifactId: string): Promise<void> {
  const current = get(artifactAcquisitionStore).downloads[artifactId];
  if (!current || isTerminal(current)) return;
  try {
    recordDownload(await cancelArtifactDownload(current.job_id));
  } catch (error) {
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
  }
}

export async function setUpLocalAi(): Promise<boolean> {
  const artifacts = get(artifactAcquisitionStore).artifacts;
  const runtime = artifacts.find((artifact) => artifact.kind === 'runtime');
  const model = artifacts.find((artifact) => artifact.kind === 'model');
  if (!runtime || !model) return false;
  artifactAcquisitionStore.update((state) => ({
    ...state,
    setup: { lifecycle: 'running', artifact_id: null },
    lastError: null
  }));
  for (const artifact of [runtime, model]) {
    artifactAcquisitionStore.update((state) => ({
      ...state,
      setup: { lifecycle: 'running', artifact_id: artifact.artifact_id }
    }));
    if (isInstalled(artifact.artifact_id)) continue;
    const terminal = await downloadApprovedArtifact(artifact.artifact_id);
    if (terminal?.lifecycle !== 'completed') {
      artifactAcquisitionStore.update((state) => ({
        ...state,
        setup: {
          lifecycle: terminal?.lifecycle === 'cancelled' ? 'cancelled' : 'failed',
          artifact_id: artifact.artifact_id
        }
      }));
      return false;
    }
    await refreshManagedRuntimeStatus();
  }
  await setManagedSelectedModel(model.artifact_id);
  const connected = await connectSelectedManagedModel();
  artifactAcquisitionStore.update((state) => ({
    ...state,
    setup: { lifecycle: connected ? 'completed' : 'failed', artifact_id: model.artifact_id },
    lastError: connected ? null : get(managedRuntimeStore).lastError
  }));
  return connected;
}

export async function removeApprovedManagedModel(modelId: string): Promise<boolean> {
  try {
    await removeManagedModel(modelId);
    await refreshManagedRuntimeStatus();
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: null }));
    return true;
  } catch (error) {
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
    return false;
  }
}

export async function setUpManagedModel(modelId: string): Promise<boolean> {
  const artifacts = get(artifactAcquisitionStore).artifacts;
  const model = artifacts.find((candidate) => candidate.artifact_id === modelId);
  if (!model) return false;
  return setUpManagedArtifactsForModel(artifacts, model);
}

export async function downloadAndSetupManagedModel(modelId: string): Promise<boolean> {
  const artifacts = get(artifactAcquisitionStore).artifacts;
  const model = artifacts.find((candidate) => candidate.artifact_id === modelId);
  if (!model) return false;
  return setUpManagedArtifactsForModel(artifacts, model);
}

async function setUpManagedArtifactsForModel(artifacts: readonly ApprovedDownloadableArtifact[], model: ApprovedDownloadableArtifact): Promise<boolean> {
  const runtime = artifacts.find((artifact) => artifact.kind === 'runtime');
  if (!runtime) return false;
  artifactAcquisitionStore.update((state) => ({
    ...state,
    setup: { lifecycle: 'running', artifact_id: null },
    lastError: null
  }));
  for (const artifact of [runtime, model]) {
    artifactAcquisitionStore.update((state) => ({
      ...state,
      setup: { lifecycle: 'running', artifact_id: artifact.artifact_id }
    }));
    if (isInstalled(artifact.artifact_id)) continue;
    const terminal = await downloadApprovedArtifact(artifact.artifact_id);
    if (terminal?.lifecycle !== 'completed') {
      artifactAcquisitionStore.update((state) => ({
        ...state,
        setup: {
          lifecycle: terminal?.lifecycle === 'cancelled' ? 'cancelled' : 'failed',
          artifact_id: artifact.artifact_id
        }
      }));
      return false;
    }
    await refreshManagedRuntimeStatus();
  }
  await setManagedSelectedModel(model.artifact_id);
  const connected = await connectSelectedManagedModel();
  artifactAcquisitionStore.update((state) => ({
    ...state,
    setup: { lifecycle: connected ? 'completed' : 'failed', artifact_id: model.artifact_id },
    lastError: connected ? null : get(managedRuntimeStore).lastError
  }));
  return connected;
}

export function resetArtifactAcquisitionStore(): void {
  lifecycleGeneration += 1;
  initialization = null;
  artifactAcquisitionStore.set(initialState);
}

async function followDownload(started: ArtifactDownloadState): Promise<ArtifactDownloadState> {
  const generation = lifecycleGeneration;
  let current = started;
  while (!isTerminal(current) && generation === lifecycleGeneration) {
    await delay(DOWNLOAD_POLL_MS);
    current = await getArtifactDownloadState(current.job_id);
    recordDownload(current);
  }
  if (generation === lifecycleGeneration) await refreshManagedRuntimeStatus();
  return current;
}

function recordDownload(download: ArtifactDownloadState): void {
  artifactAcquisitionStore.update((state) => ({
    ...state,
    downloads: { ...state.downloads, [download.artifact_id]: download },
    lastError: download.lifecycle === 'failed'
      ? { code: download.error_code ?? 'download_failed', message: 'Approved artifact download failed' }
      : state.lastError
  }));
}

function isInstalled(artifactId: string): boolean {
  return get(managedRuntimeStore).installedArtifacts.some((artifact) =>
    artifact.artifact_id === artifactId && artifact.installation_status === 'valid'
  );
}

function isTerminal(download: ArtifactDownloadState): boolean {
  return ['cancelled', 'completed', 'failed'].includes(download.lifecycle);
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
