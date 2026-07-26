# Полный исходный код (продолжение)

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/files.ts (210 строк, 7263 байт)

````typescript
import { derived, get, writable } from 'svelte/store';
import {
  forgetSelectedFile,
  getFilesCapabilityStatus,
  listSelectedFiles,
  normalizeFileError,
  previewSelectedFile,
  selectFiles
} from '$lib/bridge/files';
import type {
  FileCapabilityError,
  FilesContextReport,
  FilesCapabilityStatus,
  SelectedFilePreview,
  SelectedFileSummary
} from '$lib/types/files';

export interface FilesState {
  readonly initialized: boolean;
  readonly capability: FilesCapabilityStatus | null;
  readonly files: readonly SelectedFileSummary[];
  readonly includedIds: readonly string[];
  readonly preview: SelectedFilePreview | null;
  readonly selecting: boolean;
  readonly previewingId: string | null;
  readonly forgettingId: string | null;
  readonly lastError: FileCapabilityError | null;
  readonly lastContextReport: FilesContextReport | null;
}

const initialState: FilesState = {
  initialized: false,
  capability: null,
  files: [],
  includedIds: [],
  preview: null,
  selecting: false,
  previewingId: null,
  forgettingId: null,
  lastError: null,
  lastContextReport: null
};

let initializationPromise: Promise<void> | null = null;

export const filesStore = writable<FilesState>(initialState);
export const filesCapabilityAvailable = derived(
  filesStore,
  (state) => state.initialized && state.capability?.available === true
);
export const includedFileIds = derived(filesStore, (state) => state.includedIds);
export const includedFilesTotals = derived(filesStore, (state) => {
  const included = new Set(state.includedIds);
  return state.files.reduce(
    (totals, file) => included.has(file.file_id)
      ? {
          bytes: totals.bytes + file.byte_size,
          characters: totals.characters + file.character_count,
          count: totals.count + 1
        }
      : totals,
    { bytes: 0, characters: 0, count: 0 }
  );
});

export async function initializeFilesCapability(): Promise<void> {
  if (get(filesStore).initialized) return;
  if (initializationPromise) return initializationPromise;
  const pending = (async () => {
    try {
      const capability = await getFilesCapabilityStatus();
      const files = capability.available ? await listSelectedFiles() : [];
      filesStore.update((state) => ({
        ...state,
        initialized: true,
        capability,
        files,
        includedIds: retainReadableIds(state.includedIds, files),
        lastError: null
      }));
    } catch (error) {
      filesStore.update((state) => ({
        ...state,
        initialized: true,
        capability: null,
        files: [],
        includedIds: [],
        preview: null,
        lastError: normalizeFileError(error)
      }));
    }
  })();
  initializationPromise = pending;
  try {
    await pending;
  } finally {
    if (initializationPromise === pending) initializationPromise = null;
  }
}

export async function addFiles(): Promise<void> {
  if (!get(filesCapabilityAvailable) || get(filesStore).selecting) return;
  filesStore.update((state) => ({ ...state, selecting: true, lastError: null }));
  try {
    const response = await selectFiles();
    filesStore.update((state) => ({
      ...state,
      files: response.files,
      includedIds: retainReadableIds(state.includedIds, response.files),
      selecting: false,
      lastContextReport: null,
      lastError: null
    }));
  } catch (error) {
    filesStore.update((state) => ({ ...state, selecting: false, lastError: normalizeFileError(error) }));
  }
}

export async function openFilePreview(fileId: string): Promise<void> {
  const state = get(filesStore);
  if (state.previewingId || !state.files.some((file) => file.file_id === fileId && file.readable)) return;
  filesStore.update((current) => ({ ...current, previewingId: fileId, preview: null, lastError: null }));
  try {
    const preview = await previewSelectedFile(fileId);
    filesStore.update((current) => ({ ...current, previewingId: null, preview, lastError: null }));
  } catch (error) {
    filesStore.update((current) => ({ ...current, previewingId: null, preview: null, lastError: normalizeFileError(error) }));
    await refreshFilesAfterReadFailure();
  }
}

export function closeFilePreview(): void {
  filesStore.update((state) => ({ ...state, preview: null }));
}

export function setFileIncluded(fileId: string, included: boolean): void {
  filesStore.update((state) => {
    const file = state.files.find((candidate) => candidate.file_id === fileId);
    if (!file?.readable) return state;
    const ids = new Set(state.includedIds);
    if (included) ids.add(fileId);
    else ids.delete(fileId);
    const ordered = state.files.filter((candidate) => ids.has(candidate.file_id)).map((candidate) => candidate.file_id);
    const maximum = state.capability?.maximum_active_context_bytes ?? 0;
    const bytes = state.files.reduce((total, candidate) => ordered.includes(candidate.file_id) ? total + candidate.byte_size : total, 0);
    if (bytes > maximum) {
      return {
        ...state,
        lastError: { code: 'LC_FILE_CONTEXT_LIMIT', message: 'Selected files exceed the active context limit' }
      };
    }
    return { ...state, includedIds: ordered, lastError: null, lastContextReport: null };
  });
}

export async function forgetFile(fileId: string): Promise<void> {
  const state = get(filesStore);
  if (state.forgettingId || !state.files.some((file) => file.file_id === fileId)) return;
  filesStore.update((current) => ({ ...current, forgettingId: fileId, lastError: null }));
  try {
    const files = await forgetSelectedFile(fileId);
    filesStore.update((current) => ({
      ...current,
      files,
      includedIds: current.includedIds.filter((id) => id !== fileId),
      preview: current.preview?.file_id === fileId ? null : current.preview,
      forgettingId: null,
      lastContextReport: null,
      lastError: null
    }));
  } catch (error) {
    filesStore.update((current) => ({ ...current, forgettingId: null, lastError: normalizeFileError(error) }));
  }
}

export function reportFilesRequestError(error: FileCapabilityError): void {
  if (!error.code.startsWith('LC_FILE_')) return;
  filesStore.update((state) => ({ ...state, lastError: error }));
}

export function reportFilesContextInclusion(report: FilesContextReport | undefined): void {
  filesStore.update((state) => ({ ...state, lastContextReport: report ?? null }));
}

export function clearFilesError(): void {
  filesStore.update((state) => ({ ...state, lastError: null }));
}

export function resetFilesStore(): void {
  initializationPromise = null;
  filesStore.set(initialState);
}

async function refreshFilesAfterReadFailure(): Promise<void> {
  try {
    const files = await listSelectedFiles();
    filesStore.update((state) => ({
      ...state,
      files,
      includedIds: retainReadableIds(state.includedIds, files)
    }));
  } catch {
    // The original sanitized read error remains authoritative in the UI.
  }
}

function retainReadableIds(ids: readonly string[], files: readonly SelectedFileSummary[]): readonly string[] {
  const allowed = new Set(files.filter((file) => file.readable).map((file) => file.file_id));
  return files.filter((file) => allowed.has(file.file_id) && ids.includes(file.file_id)).map((file) => file.file_id);
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/knowledgePreview.ts (209 строк, 7115 байт)

````typescript
import { get, writable } from 'svelte/store';
import { cancelTurn } from '$lib/bridge/controlPlane';
import {
  decideKnowledgeTurn,
  requestKnowledgePreview,
  subscribeKnowledgeInjectionEvents
} from '$lib/bridge/knowledge';
import {
  DEFAULT_KNOWLEDGE_CONTEXT_CHARS,
  DEFAULT_KNOWLEDGE_INTENT,
  DEFAULT_KNOWLEDGE_RESULTS
} from '$lib/knowledge/knowledgePreview';
import type {
  KnowledgeAction,
  KnowledgePreview,
  KnowledgeUiState
} from '$lib/knowledge/knowledgePreview';
import { startLocalModelTurn } from '$lib/stores/modelGateway';

export interface KnowledgePreviewState {
  readonly enabled: boolean;
  readonly lifecycle: KnowledgeUiState;
  readonly turnId: string | null;
  readonly pendingPrompt: string;
  readonly preview: KnowledgePreview | null;
  readonly expandedSourceIds: readonly string[];
  readonly lastError: { readonly code: string; readonly message: string } | null;
}

const initialState: KnowledgePreviewState = {
  enabled: false,
  lifecycle: 'OFF',
  turnId: null,
  pendingPrompt: '',
  preview: null,
  expandedSourceIds: [],
  lastError: null
};

let unsubscribeEvents: (() => void) | null = null;

export const knowledgePreviewStore = writable<KnowledgePreviewState>(initialState);

export function setProjectKnowledgeEnabled(enabled: boolean): void {
  const state = get(knowledgePreviewStore);
  if (isDecisionLocked(state.lifecycle)) return;
  knowledgePreviewStore.set(
    enabled
      ? { ...initialState, enabled: true }
      : initialState
  );
}

export async function prepareProjectKnowledge(turnId: string, prompt: string): Promise<boolean> {
  const current = get(knowledgePreviewStore);
  if (!current.enabled || isDecisionLocked(current.lifecycle)) return false;
  knowledgePreviewStore.set({
    enabled: true,
    lifecycle: 'RETRIEVING',
    turnId,
    pendingPrompt: prompt,
    preview: null,
    expandedSourceIds: current.expandedSourceIds,
    lastError: null
  });
  try {
    const response = await requestKnowledgePreview({
      turnId,
      intent: DEFAULT_KNOWLEDGE_INTENT,
      maxContextChars: DEFAULT_KNOWLEDGE_CONTEXT_CHARS,
      maxResults: DEFAULT_KNOWLEDGE_RESULTS
    });
    if (response.state === 'FAILED') {
      knowledgePreviewStore.update((state) => ({
        ...state,
        lifecycle: 'FAILED',
        lastError: { code: response.error.code, message: response.error.safe_message }
      }));
      return false;
    }
    knowledgePreviewStore.update((state) => ({
      ...state,
      lifecycle: 'PREVIEW_READY',
      preview: response,
      lastError: null
    }));
    return true;
  } catch (error) {
    const normalized = normalizeError(error);
    knowledgePreviewStore.update((state) => ({ ...state, lifecycle: 'FAILED', lastError: normalized }));
    return false;
  }
}

export async function retryProjectKnowledgePreview(): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  if (!state.turnId || !state.pendingPrompt || !['FAILED', 'STALE'].includes(state.lifecycle)) return false;
  return prepareProjectKnowledge(state.turnId, state.pendingPrompt);
}

export async function decideProjectKnowledge(action: KnowledgeAction): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  const preview = state.preview;
  if (!preview || state.lifecycle !== 'PREVIEW_READY') return false;
  knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'DECIDING', lastError: null }));
  try {
    const response = await decideKnowledgeTurn({
      turnId: preview.turn_id,
      injectionId: preview.injection_id,
      expectedPreviewHash: preview.preview_hash,
      action
    });
    knowledgePreviewStore.update((current) => ({
      ...current,
      lifecycle:
        response.state === 'STALE'
          ? 'STALE'
          : action === 'INCLUDE_AND_SEND'
            ? response.state === 'INJECTED' ? 'INJECTED' : 'DISPATCHING'
            : action === 'CANCEL' ? 'CANCELLED' : 'REJECTED',
      lastError: response.error
        ? { code: response.error.code, message: response.error.safe_message }
        : null
    }));
    return response.state !== 'STALE';
  } catch (error) {
    knowledgePreviewStore.update((current) => ({
      ...current,
      lifecycle: 'FAILED',
      lastError: normalizeError(error)
    }));
    return false;
  }
}

export async function cancelProjectKnowledge(): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  if (state.preview && state.lifecycle === 'PREVIEW_READY') {
    return decideProjectKnowledge('CANCEL');
  }
  if (!state.turnId || !['FAILED', 'STALE'].includes(state.lifecycle)) return false;
  try {
    await cancelTurn(state.turnId, 'user_requested');
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'CANCELLED', lastError: null }));
    return true;
  } catch (error) {
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'FAILED', lastError: normalizeError(error) }));
    return false;
  }
}

export async function sendWithoutKnowledgeAfterFailure(): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  if (!state.turnId || !state.pendingPrompt || !['FAILED', 'STALE'].includes(state.lifecycle)) return false;
  try {
    await cancelTurn(state.turnId, 'user_requested');
    await startLocalModelTurn(state.pendingPrompt);
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'REJECTED', lastError: null }));
    return true;
  } catch (error) {
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'FAILED', lastError: normalizeError(error) }));
    return false;
  }
}

export function toggleKnowledgeSource(noteId: string): void {
  knowledgePreviewStore.update((state) => {
    const expanded = new Set(state.expandedSourceIds);
    if (expanded.has(noteId)) expanded.delete(noteId);
    else expanded.add(noteId);
    return { ...state, expandedSourceIds: [...expanded] };
  });
}

export async function initializeKnowledgePreviewEvents(): Promise<void> {
  if (unsubscribeEvents) return;
  unsubscribeEvents = await subscribeKnowledgeInjectionEvents((injectionId) => {
    knowledgePreviewStore.update((state) =>
      state.preview?.injection_id === injectionId
        ? { ...state, lifecycle: 'INJECTED', lastError: null }
        : state
    );
  });
}

export function shutdownKnowledgePreviewEvents(): void {
  unsubscribeEvents?.();
  unsubscribeEvents = null;
}

export function resetKnowledgePreviewStore(): void {
  unsubscribeEvents = null;
  knowledgePreviewStore.set(initialState);
}

function isDecisionLocked(state: KnowledgeUiState): boolean {
  return ['RETRIEVING', 'PREVIEW_READY', 'DECIDING', 'DISPATCHING'].includes(state);
}

function normalizeError(error: unknown): { code: string; message: string } {
  if (typeof error === 'object' && error !== null) {
    const record = error as Record<string, unknown>;
    return {
      code: String(record.code ?? 'knowledge_error').slice(0, 64),
      message: String(record.message ?? 'Project knowledge request failed').slice(0, 240)
    };
  }
  return { code: 'knowledge_error', message: 'Project knowledge request failed' };
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/modelGateway.ts (1243 строк, 47119 байт)

````typescript
import { derived, get, writable } from 'svelte/store';
import {
  cancelModelTurn,
  getManagedInstalledArtifacts,
  getManagedModelCatalog,
  getManagedModelReadiness,
  getManagedRuntimeLogs,
  getManagedRuntimeCatalog,
  getManagedRuntimeStatus,
  getModelGatewayCatalog,
  listModelGatewayModels,
  normalizeGatewayError,
  probeModelGateway,
  setModelBinding,
  startManagedRuntime,
  startModelTurn,
  stopManagedRuntime,
  subscribeModelGatewayEvents
} from '$lib/bridge/modelGateway';
import type {
  ApprovedModelSummary,
  ApprovedRuntimeSummary,
  ArtifactValidationSummary,
  GatewayCatalog,
  GatewayStatus,
  HarnessId,
  InferenceRequestState,
  ManagedCatalogIdentity,
  ManagedInstalledArtifacts,
  ManagedModelCatalog,
  ModelReadinessSummary,
  ManagedRuntimeCatalog,
  ManagedRuntimeLogs,
  ManagedRuntimeState,
  ManagedRuntimeStatus,
  ModelBinding,
  ModelGatewayEvent,
  ModelSummary,
  SanitizedGatewayError
} from '$lib/types/modelGateway';
import {
  appendAcceptedChatTurn,
  appendAssistantChunk,
  chatMessages,
  finalizeAssistantMessage,
  setModelConnected
} from '$lib/stores/shellStore';
import { locale } from '$lib/i18n';
import { reportFilesContextInclusion, reportFilesRequestError } from '$lib/stores/files';

export const MAX_GENERATED_TEXT = 262_144;
export const MODEL_REQUEST_MAX_TOKENS = 256;
export const INFERENCE_TIMEOUTS_MS = Object.freeze({
  acceptance: 6_000,
  firstToken: 30_000,
  inactivity: 10_000,
  cancelAcknowledgement: 5_000
});
export const MANAGED_HEALTH_POLL_MS = 2_000;
const MAX_BUFFERED_EARLY_EVENTS = 2_048;

export interface ModelGatewayState {
  readonly catalog: GatewayCatalog | null;
  readonly portText: string;
  readonly harnessId: HarnessId;
  readonly models: readonly ModelSummary[];
  readonly selectedModelId: string;
  readonly binding: ModelBinding | null;
  readonly activeTurnId: string | null;
  readonly generatedText: string;
  readonly status: GatewayStatus;
  readonly modelCalled: boolean;
  readonly toolsExecuted: 0;
  readonly persistence: 'Off';
  readonly lastError: SanitizedGatewayError | null;
  readonly initialized: boolean;
}

export interface ManagedRuntimePanelState {
  readonly status: ManagedRuntimeStatus | null;
  readonly catalogIdentity: ManagedCatalogIdentity | null;
  readonly runtimeCatalog: readonly ApprovedRuntimeSummary[];
  readonly catalog: readonly ApprovedModelSummary[];
  readonly installedArtifacts: readonly ArtifactValidationSummary[];
  readonly readiness: ModelReadinessSummary | null;
  readonly selectedModelId: string;
  readonly harnessId: HarnessId;
  readonly binding: ModelBinding | null;
  readonly logs: ManagedRuntimeLogs;
  readonly lastError: SanitizedGatewayError | null;
}

const initialState: ModelGatewayState = {
  catalog: null,
  portText: '1234',
  harnessId: 'minimal',
  models: [],
  selectedModelId: '',
  binding: null,
  activeTurnId: null,
  generatedText: '',
  status: 'Not configured',
  modelCalled: false,
  toolsExecuted: 0,
  persistence: 'Off',
  lastError: null,
  initialized: false
};

const initialManagedState: ManagedRuntimePanelState = {
  status: null,
  catalogIdentity: null,
  runtimeCatalog: [],
  catalog: [],
  installedArtifacts: [],
  readiness: null,
  selectedModelId: '',
  harnessId: 'minimal',
  binding: null,
  logs: { stdout_tail: [], stderr_tail: [] },
  lastError: null
};

const initialInferenceState: InferenceRequestState = {
  lifecycle: 'idle',
  requestId: null,
  chatSessionId: null,
  modelId: null,
  submittedAtUnixMs: null,
  acceptedAtUnixMs: null,
  firstTokenAtUnixMs: null,
  terminalAtUnixMs: null,
  maxTokens: null,
  chunkCount: 0,
  nextSequence: 0,
  receivedContent: false,
  cancellationAccepted: false,
  terminalMethod: null,
  rejectedEventCount: 0,
  lastError: null
};

let unsubscribeEvents: (() => void) | null = null;
let initialized = false;
let initializationPromise: Promise<void> | null = null;
let eventSubscriptionPromise: Promise<void> | null = null;
let managedSessionCheckPromise: Promise<boolean> | null = null;
let managedConnectionPromise: Promise<boolean> | null = null;
let managedHealthTimer: ReturnType<typeof setInterval> | null = null;
let submissionInProgress = false;
let subscriptionGeneration = 0;
let bufferedEarlyEvents: ModelGatewayEvent[] = [];
type TimerName = 'acceptance' | 'firstToken' | 'inactivity' | 'cancelAcknowledgement';
const inferenceTimers: Partial<Record<TimerName, ReturnType<typeof setTimeout>>> = {};

export const modelGatewayStore = writable<ModelGatewayState>(initialState);
export const managedRuntimeStore = writable<ManagedRuntimePanelState>(initialManagedState);
export const inferenceRequestStore = writable<InferenceRequestState>(initialInferenceState);
export const inferenceBusy = derived(inferenceRequestStore, (state) =>
  ['submitted', 'accepted', 'streaming', 'cancelling'].includes(state.lifecycle)
);
export const managedConnectionBusy = writable(false);
export const managedModelReady = derived(
  [managedRuntimeStore, modelGatewayStore],
  ([managed, gateway]) => isManagedModelReadySnapshot(managed, gateway)
);
export const approvedManagedModelInstalled = derived(managedRuntimeStore, (managed) =>
  managed.catalog.some((model) =>
    managed.installedArtifacts.some((artifact) => artifact.kind === 'model' && artifact.artifact_id === model.model_id && artifact.installation_status === 'valid') &&
    model.compatible_runtime_ids.some((runtimeId) =>
      managed.installedArtifacts.some((artifact) => artifact.kind === 'runtime' && artifact.artifact_id === runtimeId && artifact.installation_status === 'valid')
    )
  )
);
managedModelReady.subscribe((ready) => setModelConnected(ready));

export async function initializeModelGateway(): Promise<void> {
  if (initialized) return;
  if (initializationPromise) return initializationPromise;
  const generation = subscriptionGeneration;
  const pendingInitialization = (async () => {
    try {
      await ensureModelEventSubscription();
      if (generation !== subscriptionGeneration) return;
      const catalog = await getModelGatewayCatalog();
      if (generation !== subscriptionGeneration) return;
      modelGatewayStore.update((state) => ({ ...state, catalog, initialized: true, status: 'Binding required' }));
      await refreshManagedRuntimeStatus();
      if (generation !== subscriptionGeneration) return;
      startManagedHealthMonitor();
      initialized = true;
    } catch (error) {
      if (generation !== subscriptionGeneration) return;
      initialized = false;
      modelGatewayStore.update((state) => ({ ...state, initialized: true, status: 'Unavailable', lastError: normalizeGatewayError(error) }));
    }
  })();
  initializationPromise = pendingInitialization;
  try {
    await pendingInitialization;
  } finally {
    if (initializationPromise === pendingInitialization) initializationPromise = null;
  }
}

export function shutdownModelGateway(): void {
  subscriptionGeneration += 1;
  unsubscribeEvents?.();
  unsubscribeEvents = null;
  eventSubscriptionPromise = null;
  initializationPromise = null;
  stopManagedHealthMonitor();
  initialized = false;
  clearInferenceTimers();
  bufferedEarlyEvents = [];
}

async function ensureModelEventSubscription(): Promise<void> {
  if (unsubscribeEvents) return;
  if (eventSubscriptionPromise) return eventSubscriptionPromise;
  const generation = subscriptionGeneration;
  const pendingSubscription = subscribeModelGatewayEvents(applyModelGatewayEvent, handleModelProtocolError).then((cleanup) => {
    if (generation !== subscriptionGeneration) {
      cleanup();
      return;
    }
    unsubscribeEvents?.();
    unsubscribeEvents = cleanup;
  });
  eventSubscriptionPromise = pendingSubscription;
  try {
    await pendingSubscription;
  } finally {
    if (eventSubscriptionPromise === pendingSubscription) eventSubscriptionPromise = null;
  }
}

function startManagedHealthMonitor(): void {
  if (managedHealthTimer) return;
  managedHealthTimer = setInterval(() => {
    if (!get(inferenceBusy) && get(managedRuntimeStore).binding) {
      void verifyLiveManagedSession();
    }
  }, MANAGED_HEALTH_POLL_MS);
}

function stopManagedHealthMonitor(): void {
  if (managedHealthTimer) clearInterval(managedHealthTimer);
  managedHealthTimer = null;
  managedSessionCheckPromise = null;
  managedConnectionPromise = null;
  managedConnectionBusy.set(false);
}

async function verifyLiveManagedSession(): Promise<boolean> {
  if (managedSessionCheckPromise) return managedSessionCheckPromise;
  const generation = subscriptionGeneration;
  const expected = get(managedRuntimeStore).binding;
  const gatewayBinding = get(modelGatewayStore).binding;
  if (
    !expected ||
    !gatewayBinding ||
    gatewayBinding.provider_id !== 'managed-llama-cpp' ||
    gatewayBinding.binding_fingerprint !== expected.binding_fingerprint
  ) return false;

  const pending = (async () => {
    try {
      const status = await getManagedRuntimeStatus();
      if (generation !== subscriptionGeneration) return false;
      const current = get(managedRuntimeStore);
      if (current.binding?.binding_fingerprint !== expected.binding_fingerprint) return false;
      const runtimeReady =
        status.state === 'Ready' &&
        status.model_state === 'Ready' &&
        status.inference_ready === true &&
        status.model_id === expected.model_id &&
        status.runtime_instance_id === expected.runtime_instance_id;
      managedRuntimeStore.update((state) => ({
        ...state,
        status,
        binding: runtimeReady ? state.binding : null,
        lastError: runtimeReady ? null : {
          code: status.state === 'Failed' ? 'runtime_unavailable' : 'model_not_ready',
          message: status.state === 'Failed' ? 'Managed runtime is unavailable' : 'Approved managed model is not ready'
        }
      }));
      if (!runtimeReady) {
        clearManagedGatewayBinding();
        return false;
      }

      const rebound = await setModelBinding({
        providerId: 'managed-llama-cpp',
        harnessId: expected.harness_id,
        modelId: expected.model_id,
        runtimeInstanceId: expected.runtime_instance_id
      });
      if (generation !== subscriptionGeneration) return false;
      const latest = get(managedRuntimeStore);
      const bindingMatches =
        latest.binding?.binding_fingerprint === expected.binding_fingerprint &&
        rebound.provider_id === expected.provider_id &&
        rebound.harness_id === expected.harness_id &&
        rebound.model_id === expected.model_id &&
        rebound.runtime_instance_id === expected.runtime_instance_id &&
        rebound.binding_fingerprint === expected.binding_fingerprint;
      if (!bindingMatches) throw { code: 'protocol_mismatch', message: 'Managed model session binding changed' };
      modelGatewayStore.update((state) => ({ ...state, binding: rebound, status: 'Bound', lastError: null }));
      return true;
    } catch (error) {
      if (generation !== subscriptionGeneration) return false;
      const normalized = normalizeGatewayError(error);
      managedRuntimeStore.update((state) => ({ ...state, binding: null, lastError: normalized }));
      clearManagedGatewayBinding();
      return false;
    }
  })();
  managedSessionCheckPromise = pending;
  try {
    return await pending;
  } finally {
    if (managedSessionCheckPromise === pending) managedSessionCheckPromise = null;
  }
}

export function setGatewayPortText(portText: string): void {
  const next = portText.replace(/[^\d]/g, '').slice(0, 5);
  modelGatewayStore.update((state) => ({
    ...state,
    portText: next,
    binding: state.binding && Number(next) === state.binding.port ? state.binding : null,
    status: state.binding && Number(next) === state.binding.port ? state.status : 'Binding required'
  }));
}

export function setGatewayHarness(harnessId: HarnessId): void {
  modelGatewayStore.update((state) => ({
    ...state,
    harnessId,
    binding: state.binding?.harness_id === harnessId ? state.binding : null,
    status: state.binding?.harness_id === harnessId ? state.status : 'Binding required'
  }));
}

export function setSelectedModel(modelId: string): void {
  modelGatewayStore.update((state) => ({
    ...state,
    selectedModelId: modelId,
    binding: state.binding?.model_id === modelId ? state.binding : null,
    status: state.binding?.model_id === modelId ? state.status : 'Binding required'
  }));
}

export async function probeGateway(): Promise<void> {
  const port = currentPort();
  modelGatewayStore.update((state) => ({ ...state, status: 'Probing', lastError: null }));
  try {
    await probeModelGateway(port);
    modelGatewayStore.update((state) => ({ ...state, status: 'Ready', lastError: null }));
  } catch (error) {
    modelGatewayStore.update((state) => ({ ...state, status: 'Unavailable', binding: null, lastError: normalizeGatewayError(error) }));
  }
}

export async function discoverModels(): Promise<void> {
  const port = currentPort();
  modelGatewayStore.update((state) => ({ ...state, status: 'Probing', lastError: null }));
  try {
    const result = await listModelGatewayModels(port);
    modelGatewayStore.update((state) => ({
      ...state,
      models: result.models,
      selectedModelId: result.models.some((model) => model.model_id === state.selectedModelId) ? state.selectedModelId : '',
      binding: null,
      status: result.models.length ? 'Binding required' : 'Unavailable',
      lastError: null
    }));
  } catch (error) {
    modelGatewayStore.update((state) => ({ ...state, status: 'Unavailable', binding: null, lastError: normalizeGatewayError(error) }));
  }
}

export async function confirmBinding(): Promise<void> {
  const state = get(modelGatewayStore);
  try {
    const binding = await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: state.harnessId,
      port: currentPort(),
      modelId: state.selectedModelId
    });
    modelGatewayStore.update((current) => ({ ...current, binding, status: 'Bound', lastError: null }));
  } catch (error) {
    modelGatewayStore.update((current) => ({ ...current, status: 'Binding required', binding: null, lastError: normalizeGatewayError(error) }));
  }
}

export async function setManagedSelectedModel(modelId: string): Promise<void> {
  const previousModelId = get(managedRuntimeStore).selectedModelId;
  managedRuntimeStore.update((state) => ({
    ...state,
    selectedModelId: modelId,
    readiness: state.readiness?.model_id === modelId ? state.readiness : null,
    binding: state.binding?.model_id === modelId ? state.binding : null,
    lastError: null
  }));
  if (previousModelId !== modelId) clearManagedGatewayBinding();
  if (!modelId) return;
  try {
    const readiness = await readManagedModelReadiness(modelId);
    managedRuntimeStore.update((state) => state.selectedModelId === modelId
      ? { ...state, readiness, binding: readiness.launchable ? state.binding : null, lastError: null }
      : state);
    if (!readiness.launchable) clearManagedGatewayBinding();
  } catch (error) {
    managedRuntimeStore.update((state) => state.selectedModelId === modelId
      ? { ...state, readiness: null, binding: null, lastError: normalizeGatewayError(error) }
      : state);
    clearManagedGatewayBinding();
  }
}

export function setManagedHarness(harnessId: HarnessId): void {
  const previousHarnessId = get(managedRuntimeStore).harnessId;
  managedRuntimeStore.update((state) => ({
    ...state,
    harnessId,
    binding: state.binding?.harness_id === harnessId ? state.binding : null
  }));
  if (previousHarnessId !== harnessId) clearManagedGatewayBinding();
}

export async function refreshManagedRuntimeStatus(): Promise<void> {
  try {
    const [status, runtimeCatalog, modelCatalog, installedArtifacts, logs] = await Promise.all([
      getManagedRuntimeStatus(),
      getManagedRuntimeCatalog(),
      getManagedModelCatalog(),
      getManagedInstalledArtifacts(),
      getManagedRuntimeLogs()
    ]);
    assertManagedTrustBundle(runtimeCatalog, modelCatalog, installedArtifacts);
    const previous = get(managedRuntimeStore);
    const defaultApprovedModel = modelCatalog.models.find((model) =>
      isInstalledLaunchable(model, runtimeCatalog.runtimes, installedArtifacts.artifacts)
    );
    const selectedModelId = modelCatalog.models.some((model) => model.model_id === previous.selectedModelId)
      ? previous.selectedModelId
      : (defaultApprovedModel?.model_id ?? '');
    const selectedModel = modelCatalog.models.find((model) => model.model_id === selectedModelId);
    const bindingTrusted =
      status.state === 'Ready' &&
      status.model_state === 'Ready' &&
      status.inference_ready &&
      previous.binding !== null &&
      previous.binding.provider_id === 'managed-llama-cpp' &&
      previous.binding.harness_id === previous.harnessId &&
      previous.binding.model_id === selectedModelId &&
      previous.binding.runtime_instance_id === status.runtime_instance_id &&
      selectedModel !== undefined &&
      isInstalledLaunchable(selectedModel, runtimeCatalog.runtimes, installedArtifacts.artifacts);
    managedRuntimeStore.update((state) => ({
      ...state,
      status,
      catalogIdentity: catalogIdentityOf(runtimeCatalog),
      runtimeCatalog: runtimeCatalog.runtimes,
      catalog: modelCatalog.models,
      installedArtifacts: installedArtifacts.artifacts,
      readiness: null,
      selectedModelId,
      logs,
      lastError: null,
      binding: bindingTrusted ? state.binding : null
    }));
    if (!bindingTrusted) clearManagedGatewayBinding();
    if (selectedModelId) await setManagedSelectedModel(selectedModelId);
    const runtimeError = status.last_error;
    if (runtimeError) {
      managedRuntimeStore.update((state) => ({
        ...state,
        lastError: { code: 'runtime_unavailable', message: runtimeError }
      }));
    }
  } catch (error) {
    managedRuntimeStore.update((state) => ({
      ...state,
      catalogIdentity: null,
      runtimeCatalog: [],
      catalog: [],
      installedArtifacts: [],
      readiness: null,
      selectedModelId: '',
      binding: null,
      lastError: normalizeGatewayError(error)
    }));
    clearManagedGatewayBinding();
  }
}

export async function startSelectedManagedRuntime(precomputedReadiness?: ModelReadinessSummary): Promise<void> {
  const state = get(managedRuntimeStore);
  if (!state.selectedModelId) return;
  try {
    const readiness = precomputedReadiness ?? await readManagedModelReadiness(state.selectedModelId);
    if (get(managedRuntimeStore).selectedModelId !== state.selectedModelId) return;
    if (!readiness.launchable) {
      managedRuntimeStore.update((current) => ({
        ...current,
        readiness,
        binding: null,
        lastError: { code: 'model_not_ready', message: 'Approved managed model and runtime artifacts are not ready' }
      }));
      clearManagedGatewayBinding();
      return;
    }
    managedRuntimeStore.update((current) => ({
      ...current,
      readiness,
      status: current.status ? {
        ...current.status,
        state: 'Starting' as ManagedRuntimeState,
        model_state: 'Loading',
        inference_ready: false
      } : current.status,
      binding: null,
      lastError: null
    }));
    clearManagedGatewayBinding();
    await startManagedRuntime(state.selectedModelId);
    const status = await getManagedRuntimeStatus();
    managedRuntimeStore.update((current) => ({
      ...current,
      status,
      lastError: status.last_error
        ? { code: 'runtime_unavailable', message: status.last_error }
        : null
    }));
  } catch (error) {
    const normalized = normalizeGatewayError(error);
    await refreshManagedRuntimeStatus();
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalized }));
    clearManagedGatewayBinding();
  }
}

export async function stopSelectedManagedRuntime(): Promise<void> {
  managedRuntimeStore.update((state) => ({
    ...state,
    status: state.status ? {
      ...state.status,
      state: 'Stopping',
      model_state: 'Unloading',
      inference_ready: false
    } : state.status,
    binding: null
  }));
  clearManagedGatewayBinding();
  try {
    await stopManagedRuntime();
  } catch (error) {
    managedRuntimeStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
  }
  await refreshManagedRuntimeStatus();
}

export async function confirmManagedBinding(precomputedReadiness?: ModelReadinessSummary): Promise<void> {
  const state = get(managedRuntimeStore);
  const runtimeInstanceId = state.status?.runtime_instance_id ?? '';
  if (
    !state.selectedModelId ||
    !runtimeInstanceId ||
    state.status?.state !== 'Ready' ||
    state.status.model_state !== 'Ready' ||
    state.status.inference_ready !== true ||
    state.status.model_id !== state.selectedModelId ||
    !state.readiness?.launchable
  ) return;
  try {
    const readiness = precomputedReadiness ?? await readManagedModelReadiness(state.selectedModelId);
    const current = get(managedRuntimeStore);
    if (
      !readiness.launchable ||
      current.selectedModelId !== state.selectedModelId ||
      current.harnessId !== state.harnessId ||
      current.status?.state !== 'Ready' ||
      current.status.model_state !== 'Ready' ||
      current.status.inference_ready !== true ||
      current.status.model_id !== state.selectedModelId ||
      current.status.runtime_instance_id !== runtimeInstanceId
    ) {
      managedRuntimeStore.update((value) => ({ ...value, readiness, binding: null }));
      clearManagedGatewayBinding();
      return;
    }
    const binding = await setModelBinding({
      providerId: 'managed-llama-cpp',
      harnessId: state.harnessId,
      modelId: state.selectedModelId,
      runtimeInstanceId
    });
    managedRuntimeStore.update((value) => ({ ...value, readiness, binding, lastError: null }));
    modelGatewayStore.update((value) => ({ ...value, binding, status: 'Bound', lastError: null }));
  } catch (error) {
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalizeGatewayError(error) }));
    clearManagedGatewayBinding();
  }
}

export function connectSelectedManagedModel(): Promise<boolean> {
  if (managedConnectionPromise) return managedConnectionPromise;
  managedConnectionBusy.set(true);
  managedRuntimeStore.update((current) => ({
    ...current,
    lastError: null
  }));
  const pending = connectSelectedManagedModelOnce().finally(() => {
    if (managedConnectionPromise === pending) managedConnectionPromise = null;
    managedConnectionBusy.set(false);
  });
  managedConnectionPromise = pending;
  return pending;
}

async function connectSelectedManagedModelOnce(): Promise<boolean> {
  let state = get(managedRuntimeStore);
  if (!state.selectedModelId) {
    managedRuntimeStore.update((current) => ({
      ...current,
      lastError: { code: 'model_not_selected', message: 'No approved managed model is selected' }
    }));
    return false;
  }
  try {
    const readiness = await readManagedModelReadiness(state.selectedModelId);
    managedRuntimeStore.update((current) => ({ ...current, readiness, lastError: null }));
    if (!readiness.launchable) {
      throw { code: 'model_not_ready', message: 'Approved managed model and runtime artifacts are not ready' };
    }

    state = get(managedRuntimeStore);
    const runningSelectedModel =
      state.status?.state === 'Ready' &&
      state.status.model_state === 'Ready' &&
      state.status.inference_ready === true &&
      state.status.model_id === state.selectedModelId;
    if (!runningSelectedModel) {
      if (state.status?.state === 'Ready') await stopSelectedManagedRuntime();
      await startSelectedManagedRuntime(readiness);
    }

    state = get(managedRuntimeStore);
    if (
      state.status?.state !== 'Ready' ||
      state.status.model_state !== 'Ready' ||
      state.status.inference_ready !== true ||
      state.status.model_id !== state.selectedModelId
    ) {
      if (!state.lastError) {
        managedRuntimeStore.update((current) => ({
          ...current,
          binding: null,
          lastError: { code: 'runtime_not_ready', message: 'Managed runtime did not become ready' }
        }));
        clearManagedGatewayBinding();
      }
      return false;
    }
    await confirmManagedBinding(readiness);
    return get(managedModelReady);
  } catch (error) {
    const normalized = normalizeGatewayError(error);
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalized }));
    clearManagedGatewayBinding();
    return false;
  }
}

export async function startLocalModelTurn(
  prompt: string,
  chatSessionId = 'local-chat',
  fileIds: readonly string[] = []
): Promise<boolean> {
  const cleanPrompt = prompt.slice(0, 12_000).trim();
  if (!cleanPrompt || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(chatSessionId)) return false;
  if (submissionInProgress || get(inferenceBusy)) return false;
  submissionInProgress = true;
  try {
    return await startClaimedLocalModelTurn(cleanPrompt, chatSessionId, fileIds);
  } finally {
    submissionInProgress = false;
  }
}

async function startClaimedLocalModelTurn(
  cleanPrompt: string,
  chatSessionId: string,
  fileIds: readonly string[]
): Promise<boolean> {
  if (!get(managedModelReady)) {
    const error = { code: 'model_not_ready', message: 'Approved managed model is not ready' };
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required', lastError: error }));
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'idle', lastError: error }));
    return false;
  }

  try {
    await ensureModelEventSubscription();
  } catch (error) {
    const normalized = normalizeGatewayError(error);
    modelGatewayStore.update((state) => ({ ...state, status: 'Unavailable', lastError: normalized }));
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'failed', lastError: normalized }));
    return false;
  }

  if (!(await verifyLiveManagedSession())) {
    const error = get(managedRuntimeStore).lastError ?? { code: 'model_session_unavailable', message: 'Managed model session is unavailable' };
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required', lastError: error }));
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'idle', lastError: error }));
    return false;
  }

  const gateway = get(modelGatewayStore);
  const managed = get(managedRuntimeStore);
  const binding = gateway.binding;
  if (!binding || !isManagedModelReadySnapshot(managed, gateway)) return false;

  let requestId: string;
  try {
    requestId = createInferenceRequestId();
  } catch (error) {
    const normalized = normalizeGatewayError(error);
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'failed', lastError: normalized }));
    return false;
  }
  const submittedAtUnixMs = Date.now();
  clearInferenceTimers();
  bufferedEarlyEvents = [];
  inferenceRequestStore.set({
    lifecycle: 'submitted',
    requestId,
    chatSessionId,
    modelId: binding.model_id,
    submittedAtUnixMs,
    acceptedAtUnixMs: null,
    firstTokenAtUnixMs: null,
    terminalAtUnixMs: null,
    maxTokens: MODEL_REQUEST_MAX_TOKENS,
    chunkCount: 0,
    nextSequence: 0,
    receivedContent: false,
    cancellationAccepted: false,
    terminalMethod: null,
    rejectedEventCount: 0,
    lastError: null
  });
  scheduleInferenceTimeout('acceptance', INFERENCE_TIMEOUTS_MS.acceptance, requestId);

  try {
    const acceptance = await startModelTurn({
      requestId,
      chatSessionId,
      modelId: binding.model_id,
      submittedAtUnixMs,
      maxTokens: MODEL_REQUEST_MAX_TOKENS,
      prompt: cleanPrompt,
      fileIds,
      locale: get(locale),
      bindingFingerprint: binding.binding_fingerprint
    });
    reportFilesContextInclusion(acceptance.file_context);
    const current = get(inferenceRequestStore);
    if (
      current.requestId !== requestId ||
      !['submitted', 'cancelling', 'cancelled'].includes(current.lifecycle)
    ) return false;
    clearInferenceTimer('acceptance');
    if (!appendAcceptedChatTurn(requestId, cleanPrompt)) {
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'chat_reducer_error',
        message: 'Unable to create the accepted chat response'
      });
      return false;
    }
    if (current.lifecycle === 'cancelled') {
      finalizeAssistantMessage(requestId, 'cancelled');
      bufferedEarlyEvents = [];
      return true;
    }
    const cancelling = current.lifecycle === 'cancelling';
    inferenceRequestStore.update((state) => ({
      ...state,
      lifecycle: cancelling ? 'cancelling' : 'accepted',
      acceptedAtUnixMs: Date.now(),
      lastError: null
    }));
    modelGatewayStore.update((state) => ({
      ...state,
      status: cancelling ? 'Cancelling' : 'Generating',
      activeTurnId: requestId,
      generatedText: '',
      modelCalled: false,
      toolsExecuted: 0,
      persistence: 'Off',
      lastError: null
    }));
    if (!cancelling) scheduleInferenceTimeout('firstToken', INFERENCE_TIMEOUTS_MS.firstToken, requestId);
    drainBufferedEarlyEvents(requestId);
    return true;
  } catch (error) {
    const current = get(inferenceRequestStore);
    if (current.requestId !== requestId || isInferenceTerminal(current.lifecycle)) return false;
    if (current.lifecycle === 'cancelling') {
      terminalizeCurrentRequest('cancelled', 'model.turn.cancelled');
      return false;
    }
    clearInferenceTimers();
    bufferedEarlyEvents = [];
    const normalized = normalizeGatewayError(error);
    reportFilesRequestError(normalized);
    inferenceRequestStore.update((state) => ({
      ...state,
      lifecycle: 'failed',
      terminalAtUnixMs: Date.now(),
      terminalMethod: 'model.turn.failed',
      lastError: normalized
    }));
    modelGatewayStore.update((state) => ({ ...state, status: 'Failed', activeTurnId: null, lastError: normalized }));
    return false;
  }
}

export async function cancelLocalModelTurn(): Promise<void> {
  const current = get(inferenceRequestStore);
  const requestId = current.requestId;
  if (!requestId || !['submitted', 'accepted', 'streaming'].includes(current.lifecycle)) return;
  clearInferenceTimer('acceptance');
  clearInferenceTimer('firstToken');
  clearInferenceTimer('inactivity');
  inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'cancelling', lastError: null }));
  modelGatewayStore.update((state) => ({ ...state, status: 'Cancelling' }));
  scheduleInferenceTimeout('cancelAcknowledgement', INFERENCE_TIMEOUTS_MS.cancelAcknowledgement, requestId);
  try {
    const acknowledgement = await cancelModelTurn(requestId);
    const state = get(inferenceRequestStore);
    if (state.requestId !== requestId || isInferenceTerminal(state.lifecycle)) return;
    if (acknowledgement.already_terminal) {
      // Completion, failure, or timeout may have won the race immediately before
      // cancellation. Await that authoritative terminal under the existing bound.
      scheduleInferenceTimeout('cancelAcknowledgement', INFERENCE_TIMEOUTS_MS.cancelAcknowledgement, requestId);
      return;
    }
    if (!acknowledgement.accepted) {
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'cancel_rejected',
        message: 'Model request cancellation was rejected'
      });
      return;
    }
    inferenceRequestStore.update((value) => ({ ...value, lifecycle: 'cancelling', cancellationAccepted: true }));
    if (acknowledgement.state === 'Cancelled' && !acknowledgement.worker_alive) {
      terminalizeCurrentRequest('cancelled', 'model.turn.cancelled');
      return;
    }
    scheduleInferenceTimeout('cancelAcknowledgement', INFERENCE_TIMEOUTS_MS.cancelAcknowledgement, requestId);
  } catch (error) {
    const state = get(inferenceRequestStore);
    if (state.requestId === requestId && !isInferenceTerminal(state.lifecycle)) {
      terminalizeCurrentRequest('failed', 'model.turn.failed', normalizeGatewayError(error));
    }
  }
}

export async function retryLocalModelTurn(requestId: string, chatSessionId = 'local-chat'): Promise<boolean> {
  if (!/^[0-9a-f]{24}$/.test(requestId) || get(inferenceBusy) || !get(managedModelReady)) return false;
  const messages = get(chatMessages);
  const assistant = messages.find((message) => message.role === 'assistant' && message.requestId === requestId);
  if (!assistant || !['cancelled', 'timed_out', 'failed'].includes(assistant.state ?? '')) return false;
  const prompt = messages.find((message) => message.role === 'user' && message.requestId === requestId)?.body;
  if (!prompt) return false;
  return startLocalModelTurn(prompt, chatSessionId);
}

export function applyModelGatewayEvent(event: ModelGatewayEvent): void {
  const current = get(inferenceRequestStore);
  if (!current.requestId || event.request_id !== current.requestId || event.turn_id !== current.requestId || event.reply_to !== current.requestId) return;
  if (event.chat_session_id !== current.chatSessionId || event.model_id !== current.modelId) {
    failProtocol('Model event identity does not match the active request');
    return;
  }
  const binding = get(modelGatewayStore).binding;
  if (
    !binding ||
    event.binding_fingerprint !== binding.binding_fingerprint ||
    event.provider_id !== binding.provider_id ||
    event.harness_id !== binding.harness_id
  ) {
    failProtocol('Model event binding does not match the active request');
    return;
  }
  if (isInferenceTerminal(current.lifecycle)) {
    inferenceRequestStore.update((state) => ({ ...state, rejectedEventCount: state.rejectedEventCount + 1 }));
    return;
  }
  if (current.lifecycle === 'submitted') {
    if (event.sequence !== bufferedEarlyEvents.length || bufferedEarlyEvents.length >= MAX_BUFFERED_EARLY_EVENTS) {
      failProtocol('Early model event sequence is invalid');
      return;
    }
    bufferedEarlyEvents.push(event);
    return;
  }
  applyAcceptedModelEvent(event);
}

function applyAcceptedModelEvent(event: ModelGatewayEvent): void {
  const current = get(inferenceRequestStore);
  if (event.sequence !== current.nextSequence) {
    failProtocol('Model event sequence is not consecutive');
    return;
  }
  inferenceRequestStore.update((state) => ({ ...state, nextSequence: state.nextSequence + 1 }));

  if (event.method === 'model.turn.started') {
    if (current.lifecycle !== 'accepted' && current.lifecycle !== 'cancelling') {
      failProtocol('Duplicate model start event rejected');
      return;
    }
    const cancelling = current.lifecycle === 'cancelling';
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: cancelling ? 'cancelling' : 'streaming' }));
    modelGatewayStore.update((state) => ({ ...state, status: cancelling ? 'Cancelling' : 'Generating', activeTurnId: event.request_id, modelCalled: event.model_called }));
    return;
  }

  if (event.method === 'model.output.delta') {
    if (current.lifecycle === 'cancelling') return;
    if (!event.text) return;
    appendAssistantChunk(event.request_id, event.text);
    clearInferenceTimer('firstToken');
    scheduleInferenceTimeout('inactivity', INFERENCE_TIMEOUTS_MS.inactivity, event.request_id);
    inferenceRequestStore.update((state) => ({
      ...state,
      lifecycle: 'streaming',
      receivedContent: true,
      firstTokenAtUnixMs: state.firstTokenAtUnixMs ?? Date.now(),
      chunkCount: state.chunkCount + 1
    }));
    modelGatewayStore.update((state) => ({
      ...state,
      status: 'Generating',
      modelCalled: event.model_called,
      generatedText: `${state.generatedText}${event.text}`.slice(0, MAX_GENERATED_TEXT)
    }));
    return;
  }

  const latest = get(inferenceRequestStore);
  if (
    latest.lifecycle === 'cancelling' &&
    latest.cancellationAccepted &&
    ['model.turn.completed', 'model.turn.timed_out', 'model.turn.failed'].includes(event.method)
  ) {
    inferenceRequestStore.update((state) => ({ ...state, rejectedEventCount: state.rejectedEventCount + 1 }));
    return;
  }
  if (event.method === 'model.turn.completed') {
    if (!latest.receivedContent) {
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'empty_model_response',
        message: 'Model completed without response content'
      });
      return;
    }
    terminalizeCurrentRequest('completed', event.method);
    return;
  }
  if (event.method === 'model.turn.cancelled') {
    terminalizeCurrentRequest('cancelled', event.method);
    return;
  }
  if (event.method === 'model.turn.timed_out') {
    terminalizeCurrentRequest('timed_out', event.method, event.error ?? {
      code: 'request_timed_out',
      message: 'Model request timed out'
    });
    return;
  }
  terminalizeCurrentRequest('failed', event.method, event.error ?? {
    code: 'model_request_failed',
    message: 'Model request failed'
  });
}

function drainBufferedEarlyEvents(requestId: string): void {
  const events = bufferedEarlyEvents;
  bufferedEarlyEvents = [];
  for (const event of events) {
    const current = get(inferenceRequestStore);
    if (current.requestId !== requestId || isInferenceTerminal(current.lifecycle)) break;
    applyAcceptedModelEvent(event);
  }
}

function terminalizeCurrentRequest(
  lifecycle: 'completed' | 'cancelled' | 'timed_out' | 'failed',
  method: ModelGatewayEvent['method'],
  error: SanitizedGatewayError | null = null
): boolean {
  const current = get(inferenceRequestStore);
  if (!current.requestId || isInferenceTerminal(current.lifecycle)) return false;
  clearInferenceTimers();
  bufferedEarlyEvents = [];
  finalizeAssistantMessage(current.requestId, lifecycle, error?.message);
  inferenceRequestStore.set({
    ...current,
    lifecycle,
    terminalAtUnixMs: Date.now(),
    terminalMethod: method,
    lastError: error
  });
  modelGatewayStore.update((state) => ({
    ...state,
    status: lifecycle === 'completed' ? 'Completed' : lifecycle === 'cancelled' ? 'Cancelled' : 'Failed',
    activeTurnId: null,
    lastError: error
  }));
  return true;
}

function failProtocol(message: string): void {
  const requestId = get(inferenceRequestStore).requestId;
  if (terminalizeCurrentRequest('failed', 'model.turn.failed', { code: 'protocol_mismatch', message }) && requestId) {
    void cancelModelTurn(requestId).catch(() => undefined);
  }
}

function handleModelProtocolError(): void {
  if (get(inferenceBusy)) {
    failProtocol('Invalid typed model event received');
    return;
  }
  modelGatewayStore.update((state) => ({
    ...state,
    lastError: { code: 'protocol_mismatch', message: 'Invalid typed model event received' }
  }));
}

function scheduleInferenceTimeout(name: TimerName, delayMs: number, requestId: string): void {
  clearInferenceTimer(name);
  inferenceTimers[name] = setTimeout(() => {
    delete inferenceTimers[name];
    const current = get(inferenceRequestStore);
    if (current.requestId !== requestId || isInferenceTerminal(current.lifecycle)) return;
    const error = timeoutError(name);
    terminalizeCurrentRequest('timed_out', 'model.turn.timed_out', error);
    void cancelModelTurn(requestId).catch(() => undefined);
  }, delayMs);
}

function timeoutError(name: TimerName): SanitizedGatewayError {
  if (name === 'acceptance') return { code: 'request_acceptance_timeout', message: 'Model request acceptance timed out' };
  if (name === 'firstToken') return { code: 'first_token_timeout', message: 'Model response did not produce a token in time' };
  if (name === 'inactivity') return { code: 'stream_inactivity_timeout', message: 'Model response stream was interrupted' };
  return { code: 'cancel_ack_timeout', message: 'Model request cancellation timed out' };
}

function clearInferenceTimer(name: TimerName): void {
  const timer = inferenceTimers[name];
  if (timer !== undefined) clearTimeout(timer);
  delete inferenceTimers[name];
}

function clearInferenceTimers(): void {
  clearInferenceTimer('acceptance');
  clearInferenceTimer('firstToken');
  clearInferenceTimer('inactivity');
  clearInferenceTimer('cancelAcknowledgement');
}

function isInferenceTerminal(lifecycle: InferenceRequestState['lifecycle']): boolean {
  return lifecycle === 'completed' || lifecycle === 'cancelled' || lifecycle === 'timed_out' || lifecycle === 'failed';
}

function createInferenceRequestId(): string {
  if (!globalThis.crypto?.getRandomValues) {
    throw { code: 'runtime_unavailable', message: 'Secure request identifier generation is unavailable' };
  }
  const bytes = new Uint8Array(12);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function readManagedModelReadiness(modelId: string): Promise<ModelReadinessSummary> {
  const state = get(managedRuntimeStore);
  const identity = state.catalogIdentity;
  const model = state.catalog.find((candidate) => candidate.model_id === modelId);
  if (!identity || !model) throw trustPayloadError();
  const readiness = await getManagedModelReadiness(modelId);
  assertSameCatalogIdentity(identity, readiness);
  if (!sameStrings(readiness.compatible_runtime_ids, model.compatible_runtime_ids)) throw trustPayloadError();
  if (readiness.selected_runtime_id && !state.runtimeCatalog.some((runtime) => runtime.runtime_id === readiness.selected_runtime_id)) {
    throw trustPayloadError();
  }
  return readiness;
}

function assertManagedTrustBundle(
  runtimeCatalog: ManagedRuntimeCatalog,
  modelCatalog: ManagedModelCatalog,
  installedArtifacts: ManagedInstalledArtifacts
): void {
  assertSameCatalogIdentity(runtimeCatalog, modelCatalog);
  assertSameCatalogIdentity(runtimeCatalog, installedArtifacts);
  const runtimes = new Map(runtimeCatalog.runtimes.map((runtime) => [runtime.runtime_id, runtime] as const));
  const models = new Map(modelCatalog.models.map((model) => [model.model_id, model] as const));
  for (const model of modelCatalog.models) {
    if (model.compatible_runtime_ids.some((runtimeId) => !runtimes.has(runtimeId))) throw trustPayloadError();
  }
  if (installedArtifacts.artifacts.length !== runtimes.size + models.size) throw trustPayloadError();
  for (const artifact of installedArtifacts.artifacts) {
    const approved = artifact.kind === 'runtime' ? runtimes.get(artifact.artifact_id) : models.get(artifact.artifact_id);
    if (
      !approved ||
      approved.status !== artifact.catalog_status ||
      approved.asset_bytes !== artifact.expected_bytes ||
      approved.asset_sha256 !== artifact.expected_sha256
    ) throw trustPayloadError();
  }
}

function assertSameCatalogIdentity(left: ManagedCatalogIdentity, right: ManagedCatalogIdentity): void {
  if (
    left.schema_version !== right.schema_version ||
    left.catalog_id !== right.catalog_id ||
    left.catalog_version !== right.catalog_version ||
    left.catalog_digest !== right.catalog_digest
  ) throw trustPayloadError();
}

function catalogIdentityOf(value: ManagedCatalogIdentity): ManagedCatalogIdentity {
  return {
    schema_version: value.schema_version,
    catalog_id: value.catalog_id,
    catalog_version: value.catalog_version,
    catalog_digest: value.catalog_digest
  };
}

function isInstalledLaunchable(
  model: ApprovedModelSummary,
  runtimes: readonly ApprovedRuntimeSummary[],
  installedArtifacts: readonly ArtifactValidationSummary[]
): boolean {
  const modelValidation = installedArtifacts.find((artifact) => artifact.kind === 'model' && artifact.artifact_id === model.model_id);
  if (modelValidation?.installation_status !== 'valid') return false;
  return model.compatible_runtime_ids.some((runtimeId) =>
    runtimes.some((runtime) => runtime.runtime_id === runtimeId) &&
    installedArtifacts.some((artifact) =>
      artifact.kind === 'runtime' && artifact.artifact_id === runtimeId && artifact.installation_status === 'valid'
    )
  );
}

export function isManagedModelReadySnapshot(
  managed: ManagedRuntimePanelState,
  gateway: ModelGatewayState
): boolean {
  const selectedModelId = managed.selectedModelId;
  const status = managed.status;
  const readiness = managed.readiness;
  const binding = managed.binding;
  if (
    !selectedModelId ||
    !status ||
    status.state !== 'Ready' ||
    status.model_state !== 'Ready' ||
    status.inference_ready !== true ||
    status.model_id !== selectedModelId ||
    !status.runtime_instance_id ||
    !status.binding_fingerprint ||
    !readiness ||
    readiness.model_id !== selectedModelId ||
    !readiness.launchable ||
    !binding ||
    binding.provider_id !== 'managed-llama-cpp' ||
    binding.harness_id !== managed.harnessId ||
    binding.model_id !== selectedModelId ||
    binding.runtime_instance_id !== status.runtime_instance_id ||
    gateway.binding?.provider_id !== 'managed-llama-cpp' ||
    gateway.binding.harness_id !== managed.harnessId ||
    gateway.binding.model_id !== selectedModelId ||
    gateway.binding.runtime_instance_id !== status.runtime_instance_id ||
    gateway.binding.binding_fingerprint !== binding.binding_fingerprint
  ) return false;

  const modelInstalled = managed.installedArtifacts.some((artifact) =>
    artifact.kind === 'model' && artifact.artifact_id === selectedModelId && artifact.installation_status === 'valid'
  );
  const runtimeInstalled = readiness.selected_runtime_id !== null && managed.installedArtifacts.some((artifact) =>
    artifact.kind === 'runtime' && artifact.artifact_id === readiness.selected_runtime_id && artifact.installation_status === 'valid'
  );
  return modelInstalled && runtimeInstalled;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function trustPayloadError(): SanitizedGatewayError {
  return { code: 'invalid_payload', message: 'Invalid managed artifact trust payload' };
}

function clearManagedGatewayBinding(): void {
  modelGatewayStore.update((state) => state.binding?.provider_id === 'managed-llama-cpp'
    ? { ...state, binding: null, status: 'Binding required' }
    : state);
}

export function resetModelGatewayStore(): void {
  subscriptionGeneration += 1;
  initialized = false;
  initializationPromise = null;
  eventSubscriptionPromise = null;
  unsubscribeEvents?.();
  unsubscribeEvents = null;
  stopManagedHealthMonitor();
  submissionInProgress = false;
  clearInferenceTimers();
  bufferedEarlyEvents = [];
  modelGatewayStore.set(initialState);
  managedRuntimeStore.set(initialManagedState);
  managedConnectionPromise = null;
  managedConnectionBusy.set(false);
  inferenceRequestStore.set(initialInferenceState);
}

function currentPort(): number {
  const value = Number(get(modelGatewayStore).portText);
  if (!Number.isInteger(value) || value < 1024 || value > 65535) {
    throw { code: 'invalid_payload', message: 'Port must be 1024-65535' };
  }
  return value;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/reviewCenter.ts (821 строк, 28805 байт)

````typescript
import { derived, get, writable } from 'svelte/store';
import {
  HUMAN_REVIEW_DECISION_CONTRACT,
  KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
  KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
  KNOWLEDGE_REVIEW_ACTOR_SOURCE,
  KNOWLEDGE_REVIEW_LIST_LIMIT,
  KNOWLEDGE_REVIEW_LIST_OFFSET,
  MAX_KNOWLEDGE_REVIEW_LIST_OFFSET,
  KNOWLEDGE_REVIEW_PROJECTION_CONTRACT,
  knowledgeReviewClient,
  normalizeKnowledgeReviewError,
  reviewProjectionToCenterItem,
  reviewSummaryToQueueItem,
  type KnowledgeReviewClient
} from '$lib/bridge/knowledgeReview';
import type {
  DecisionDialogState,
  DecisionIntent,
  FixtureDecisionResult,
  KnowledgeReviewSnapshotEnvelope,
  RealDecisionResult,
  RealReviewCenterItem,
  ReviewActivityEvent,
  ReviewCenterItem,
  ReviewCenterState,
  ReviewDecisionResult,
  ReviewDiagnostics,
  ReviewFilterState,
  ReviewOperation,
  ReviewQueueItem,
  ReviewStatus
} from '$lib/types/knowledgeReview';

export const MAX_REVIEW_COMMENT_LENGTH = 2000;
export const MAX_REVIEW_ACTIVITY_ITEMS = 128;
export const DEFAULT_REVIEW_ACTOR_IDENTIFIER = 'local-user';
export const DEFAULT_REVIEW_ACTOR_DISPLAY_NAME = 'Local user';

const INITIAL_DIALOG: DecisionDialogState = Object.freeze({
  open: false,
  intent: null,
  comment: '',
  actorIdentifier: DEFAULT_REVIEW_ACTOR_IDENTIFIER,
  actorDisplayName: DEFAULT_REVIEW_ACTOR_DISPLAY_NAME,
  submitting: false,
  errorKey: null
});

const INITIAL_REVIEW_CENTER_STATE: ReviewCenterState = Object.freeze({
  status: 'idle',
  source: 'LOCAL_CONTROL_PLANE',
  error: null,
  failedRequest: null,
  retryable: false,
  totalCount: 0,
  returnedCount: 0,
  truncated: false,
  nextOffset: null
});

const INITIAL_FILTERS: ReviewFilterState = Object.freeze({
  query: '',
  statuses: Object.freeze([]),
  operations: Object.freeze([]),
  sort: 'STATUS_THEN_IDENTITY'
});

const STATUS_ORDER: Readonly<Record<ReviewStatus, number>> = Object.freeze({
  BLOCKED: 0,
  REVIEW_REQUIRED: 1,
  CLEAR: 2
});

export function createReviewCenterController(client: KnowledgeReviewClient = knowledgeReviewClient) {
  const reviewCenterState = writable<ReviewCenterState>(INITIAL_REVIEW_CENTER_STATE);
  const reviewQueue = writable<readonly ReviewQueueItem[]>([]);
  const selectedReviewId = writable<string | null>(null);
  const selectedReview = writable<ReviewCenterItem | null>(null);
  const reviewSnapshot = writable<KnowledgeReviewSnapshotEnvelope | null>(null);
  const decisionDialog = writable<DecisionDialogState>(INITIAL_DIALOG);
  const decisionResult = writable<ReviewDecisionResult | null>(null);
  const fixtureDecisionResult = derived(decisionResult, ($result) =>
    $result?.fixture === true ? $result : null
  );
  const realDecisionResult = derived(decisionResult, ($result) =>
    $result?.fixture === false ? $result : null
  );
  const reviewFilters = writable<ReviewFilterState>(INITIAL_FILTERS);
  const reviewActivity = writable<readonly ReviewActivityEvent[]>([]);

  const filteredReviewQueue = derived(
    [reviewQueue, reviewFilters],
    ([$queue, $filters]) => filterAndSortQueue($queue, $filters)
  );

  const reviewDiagnostics = derived(
    [reviewSnapshot, reviewCenterState],
    ([$snapshot, $state]): ReviewDiagnostics => Object.freeze({
      commandCenterVersion: KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
      frontendContractVersion: KNOWLEDGE_REVIEW_PROJECTION_CONTRACT,
      tauriBridgeStatus:
        $state.status === 'idle'
          ? 'IDLE'
          : $state.status === 'loading'
            ? 'CONNECTING'
            : $state.status === 'error'
              ? 'ERROR'
              : 'CONNECTED',
      sidecarConnectionState:
        $state.status === 'idle'
          ? 'IDLE'
          : $state.status === 'loading'
            ? 'CONNECTING'
            : $state.error?.code === 'sidecar_unavailable'
              ? 'UNAVAILABLE'
              : $state.status === 'error'
                ? 'ERROR'
                : 'CONNECTED',
      pythonRuntimeContractVersion: $snapshot?.sidecar_runtime_version ?? null,
      inboxCount: $snapshot?.inbox_count ?? $state.totalCount,
      staleCount: $snapshot?.stale_count ?? 0,
      blockedCount: $snapshot?.blocked_count ?? 0,
      sessionDecisionCount: $snapshot?.session_decision_count ?? 0,
      currentVaultRevision: $snapshot?.current_vault_revision ?? null,
      freshnessKnown: $snapshot?.freshness_known ?? false,
      lastErrorCode: $snapshot?.last_error_code ?? $state.error?.code ?? null
    })
  );

  let listGeneration = 0;
  let getGeneration = 0;
  let decisionGeneration = 0;
  let activitySequence = 0;
  let listMetadata = {
    totalCount: 0,
    returnedCount: 0,
    truncated: false,
    nextOffset: null as number | null
  };

  function appendActivity(
    kind: ReviewActivityEvent['kind'],
    messageKey: string,
    reviewArtifactIdentity: string | null = null,
    errorCode: string | null = null
  ): void {
    activitySequence += 1;
    const event: ReviewActivityEvent = Object.freeze({
      id: `review-activity-${activitySequence}`,
      sequence: activitySequence,
      kind,
      messageKey,
      reviewArtifactIdentity,
      errorCode
    });
    reviewActivity.update((items) =>
      Object.freeze([...items, event].slice(-MAX_REVIEW_ACTIVITY_ITEMS))
    );
  }

  function setLoading(failedRequest: ReviewCenterState['failedRequest'] = null): void {
    reviewCenterState.set({
      status: 'loading',
      source: 'LOCAL_CONTROL_PLANE',
      error: null,
      failedRequest,
      retryable: false,
      ...listMetadata
    });
  }

  function setError(
    error: unknown,
    failedRequest: NonNullable<ReviewCenterState['failedRequest']>
  ): void {
    const normalized = normalizeKnowledgeReviewError(error);
    reviewCenterState.set({
      status: 'error',
      source: 'LOCAL_CONTROL_PLANE',
      error: normalized,
      failedRequest,
      retryable: isTransientReviewError(normalized.code),
      ...listMetadata
    });
    appendActivity('ERROR', 'review.activity.error', get(selectedReviewId), normalized.code);
  }

  function applySnapshot(
    queue: readonly ReviewQueueItem[],
    snapshot: KnowledgeReviewSnapshotEnvelope
  ): readonly ReviewQueueItem[] {
    const staleByIdentity = new Map(
      snapshot.review_states.map((item) => [item.review_artifact_identity, item.stale] as const)
    );
    return Object.freeze(
      queue.map((item) =>
        Object.freeze({
          ...item,
          stale: staleByIdentity.get(item.reviewArtifactIdentity) ?? null
        })
      )
    );
  }

  function applySelectedFreshness(
    review: RealReviewCenterItem,
    snapshot: KnowledgeReviewSnapshotEnvelope | null
  ): RealReviewCenterItem {
    const state = snapshot?.review_states.find(
      (candidate) => candidate.review_artifact_identity === review.reviewArtifactIdentity
    );
    return Object.freeze({ ...review, stale: state?.stale ?? null });
  }

  async function loadReviewCenter(options: { refresh?: boolean } = {}): Promise<boolean> {
    const currentListGeneration = ++listGeneration;
    getGeneration += 1;
    decisionGeneration += 1;
    const previousSelectedIdentity = get(selectedReviewId);
    listMetadata = { totalCount: 0, returnedCount: 0, truncated: false, nextOffset: null };
    setLoading(options.refresh ? 'refresh' : 'list');
    reviewQueue.set([]);
    selectedReviewId.set(null);
    selectedReview.set(null);
    decisionResult.set(null);
    closeDecisionDialog();

    let snapshot: KnowledgeReviewSnapshotEnvelope | null = null;
    const collected: ReviewQueueItem[] = [];
    const seenOffsets = new Set<number>();
    const seenIdentities = new Set<string>();
    let expectedTotalCount: number | null = null;
    let requestedOffset = KNOWLEDGE_REVIEW_LIST_OFFSET;
    let lastIdentity: string | null = null;

    try {
      snapshot = options.refresh ? await client.refresh() : await client.snapshot();

      while (true) {
        if (seenOffsets.has(requestedOffset)) {
          throw reviewPaginationError('Review pagination repeated an offset');
        }
        seenOffsets.add(requestedOffset);

        const envelope = await client.list(requestedOffset, KNOWLEDGE_REVIEW_LIST_LIMIT);
        if (expectedTotalCount === null) {
          expectedTotalCount = envelope.total_count;
        } else if (envelope.total_count !== expectedTotalCount) {
          throw reviewPaginationError('Review pagination total changed between pages');
        }
        if (
          envelope.offset !== requestedOffset ||
          envelope.returned_count !== envelope.items.length ||
          collected.length + envelope.returned_count > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
        ) {
          throw reviewPaginationError('Review pagination metadata is inconsistent');
        }

        for (const summary of envelope.items) {
          if (seenIdentities.has(summary.review_artifact_identity)) {
            throw reviewPaginationError('Review pagination returned a duplicate identity');
          }
          if (
            lastIdentity !== null &&
            summary.review_artifact_identity <= lastIdentity
          ) {
            throw reviewPaginationError('Review pagination order is not deterministic');
          }
          seenIdentities.add(summary.review_artifact_identity);
          lastIdentity = summary.review_artifact_identity;
          collected.push(reviewSummaryToQueueItem(summary));
        }

        listMetadata = {
          totalCount: expectedTotalCount,
          returnedCount: collected.length,
          truncated: collected.length < expectedTotalCount,
          nextOffset: envelope.next_offset
        };

        if (!envelope.truncated) {
          if (
            envelope.next_offset !== null ||
            collected.length !== expectedTotalCount
          ) {
            throw reviewPaginationError('Review pagination ended before the complete inbox');
          }
          break;
        }

        const nextOffset = envelope.next_offset;
        if (
          nextOffset === null ||
          nextOffset <= requestedOffset ||
          nextOffset !== requestedOffset + envelope.returned_count ||
          nextOffset !== collected.length ||
          nextOffset > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
        ) {
          throw reviewPaginationError('Review pagination continuation is invalid');
        }
        requestedOffset = nextOffset;
      }
    } catch (error) {
      if (currentListGeneration !== listGeneration) return false;
      if (snapshot !== null) reviewSnapshot.set(snapshot);
      const partialQueue =
        snapshot === null ? Object.freeze([...collected]) : applySnapshot(collected, snapshot);
      reviewQueue.set(partialQueue);
      listMetadata = {
        totalCount: expectedTotalCount ?? collected.length,
        returnedCount: collected.length,
        truncated: (expectedTotalCount ?? collected.length) > collected.length,
        nextOffset:
          expectedTotalCount !== null && collected.length < expectedTotalCount
            ? requestedOffset
            : null
      };
      setError(error, options.refresh ? 'refresh' : 'list');
      return false;
    }
    if (currentListGeneration !== listGeneration || snapshot === null) return false;

    appendActivity(
      options.refresh ? 'INBOX_REFRESH' : 'SIDECAR_RECONNECT',
      options.refresh ? 'review.activity.inbox_refresh' : 'review.activity.connected'
    );
    reviewSnapshot.set(snapshot);
    listMetadata = {
      totalCount: expectedTotalCount ?? collected.length,
      returnedCount: collected.length,
      truncated: false,
      nextOffset: null
    };
    const queue = applySnapshot(collected, snapshot);
    reviewQueue.set(queue);
    if (queue.length === 0) {
      reviewCenterState.set({
        status: 'empty',
        source: 'LOCAL_CONTROL_PLANE',
        error: null,
        failedRequest: null,
        retryable: false,
        ...listMetadata
      });
      return true;
    }

    const selectedIdentity =
      previousSelectedIdentity !== null &&
      queue.some((item) => item.reviewArtifactIdentity === previousSelectedIdentity)
        ? previousSelectedIdentity
        : queue[0].reviewArtifactIdentity;
    selectedReviewId.set(selectedIdentity);
    return loadRealReview(selectedIdentity, currentListGeneration, ++getGeneration);
  }

  async function loadRealReview(
    reviewArtifactIdentity: string,
    expectedListGeneration: number,
    expectedGetGeneration: number
  ): Promise<boolean> {
    let envelope;
    try {
      envelope = await client.get(reviewArtifactIdentity);
    } catch (error) {
      if (
        expectedListGeneration !== listGeneration ||
        expectedGetGeneration !== getGeneration ||
        get(selectedReviewId) !== reviewArtifactIdentity
      ) {
        return false;
      }
      selectedReview.set(null);
      setError(error, 'get');
      return false;
    }
    if (
      expectedListGeneration !== listGeneration ||
      expectedGetGeneration !== getGeneration ||
      get(selectedReviewId) !== reviewArtifactIdentity
    ) {
      return false;
    }
    if (envelope.projection.review_artifact_identity !== reviewArtifactIdentity) {
      selectedReview.set(null);
      setError(
        Object.freeze({ code: 'invalid_payload', message: 'Review get identity mismatch' }),
        'get'
      );
      return false;
    }
    const realReview = applySelectedFreshness(
      reviewProjectionToCenterItem(envelope),
      get(reviewSnapshot)
    );
    selectedReview.set(realReview);
    reviewCenterState.set({
      status: 'ready',
      source: 'LOCAL_CONTROL_PLANE',
      error: null,
      failedRequest: null,
      retryable: false,
      ...listMetadata
    });
    appendActivity(
      realReview.stale === true ? 'STALE_REVIEW' : 'ARTIFACT_OPENED',
      realReview.stale === true
        ? 'review.activity.stale_review'
        : 'review.activity.artifact_opened',
      reviewArtifactIdentity
    );
    return true;
  }

  function selectReview(reviewId: string): boolean {
    const queueItem = get(reviewQueue).find((review) => review.id === reviewId);
    if (!queueItem) return false;
    selectedReviewId.set(reviewId);
    decisionResult.set(null);
    closeDecisionDialog();
    selectedReview.set(null);
    setLoading('get');
    void loadRealReview(reviewId, listGeneration, ++getGeneration);
    return true;
  }

  function moveReviewSelection(delta: -1 | 1): string | null {
    const reviews = get(filteredReviewQueue);
    if (reviews.length === 0) return null;
    const currentId = get(selectedReviewId);
    const currentIndex = Math.max(0, reviews.findIndex((review) => review.id === currentId));
    const nextIndex = (currentIndex + delta + reviews.length) % reviews.length;
    const nextId = reviews[nextIndex].id;
    selectReview(nextId);
    return nextId;
  }

  function selectReviewBoundary(boundary: 'first' | 'last'): string | null {
    const reviews = get(filteredReviewQueue);
    if (reviews.length === 0) return null;
    const target = boundary === 'first' ? reviews[0] : reviews[reviews.length - 1];
    selectReview(target.id);
    return target.id;
  }

  async function refreshReviewCenter(): Promise<boolean> {
    return loadReviewCenter({ refresh: true });
  }

  async function retryReviewCenter(): Promise<boolean> {
    const state = get(reviewCenterState);
    if (state.status !== 'error' || !state.retryable) return false;
    if (state.failedRequest === 'list' || state.failedRequest === 'snapshot') {
      return loadReviewCenter();
    }
    if (state.failedRequest === 'refresh') return loadReviewCenter({ refresh: true });
    if (state.failedRequest !== 'get') return false;
    const reviewId = get(selectedReviewId);
    if (!reviewId) return false;
    setLoading('get');
    return loadRealReview(reviewId, listGeneration, ++getGeneration);
  }

  function openDecisionDialog(review: ReviewCenterItem, intent: DecisionIntent): boolean {
    decisionResult.set(null);
    if (intent === 'APPROVE' && review.status === 'BLOCKED') {
      decisionDialog.set({ ...INITIAL_DIALOG, errorKey: 'review.decision.blocked_approval' });
      return false;
    }
    if (review.fixture === false && review.stale !== false) {
      decisionDialog.set({
        ...INITIAL_DIALOG,
        errorKey:
          review.stale === true
            ? 'review.decision.stale'
            : 'review.decision.freshness_unknown'
      });
      return false;
    }
    decisionDialog.set({
      ...INITIAL_DIALOG,
      open: true,
      intent
    });
    return true;
  }

  function closeDecisionDialog(): void {
    decisionDialog.set(INITIAL_DIALOG);
  }

  function setDecisionComment(rawComment: string): void {
    const comment = rawComment.slice(0, MAX_REVIEW_COMMENT_LENGTH);
    decisionDialog.update((state) => ({ ...state, comment, errorKey: null }));
  }

  function setDecisionActorIdentifier(rawValue: string): void {
    decisionDialog.update((state) => ({
      ...state,
      actorIdentifier: rawValue.slice(0, 256),
      errorKey: null
    }));
  }

  function setDecisionActorDisplayName(rawValue: string): void {
    decisionDialog.update((state) => ({
      ...state,
      actorDisplayName: rawValue.slice(0, 256),
      errorKey: null
    }));
  }

  function validateDialog(review: ReviewCenterItem, state: DecisionDialogState): string | null {
    if (!state.open || state.intent === null) return 'review.decision.unavailable';
    if (state.intent === 'APPROVE' && review.status === 'BLOCKED') {
      return 'review.decision.blocked_approval';
    }
    if (review.fixture === false && review.stale !== false) {
      return review.stale === true
        ? 'review.decision.stale'
        : 'review.decision.freshness_unknown';
    }
    if (state.intent === 'REQUEST_CHANGES' && state.comment.trim().length === 0) {
      return 'review.decision.comment_required';
    }
    if (
      state.actorIdentifier.trim().length === 0 ||
      state.actorDisplayName.trim().length === 0
    ) {
      return 'review.decision.actor_required';
    }
    return null;
  }

  function confirmFixtureDecision(review: ReviewCenterItem): boolean {
    if (review.fixture !== true) return false;
    const state = get(decisionDialog);
    const errorKey = validateDialog(review, state);
    if (errorKey) {
      decisionDialog.update((current) => ({ ...current, errorKey }));
      return false;
    }
    const result: FixtureDecisionResult = Object.freeze({
      fixture: true,
      hardStop: true,
      proposalId: review.proposalId,
      reviewArtifactIdentity: review.reviewArtifactIdentity,
      intent: state.intent as DecisionIntent,
      comment: state.comment,
      messageKey: 'review.decision.fixture_hard_stop'
    });
    decisionResult.set(result);
    closeDecisionDialog();
    return true;
  }

  async function confirmDecision(review: ReviewCenterItem): Promise<boolean> {
    if (review.fixture) return confirmFixtureDecision(review);
    const state = get(decisionDialog);
    const errorKey = validateDialog(review, state);
    if (errorKey) {
      decisionDialog.update((current) => ({ ...current, errorKey }));
      return false;
    }
    const generation = ++decisionGeneration;
    decisionDialog.update((current) => ({ ...current, submitting: true, errorKey: null }));
    try {
      const envelope = await client.createDecision({
        reviewContractVersion: KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
        proposalId: review.proposalId,
        reviewArtifactIdentity: review.reviewArtifactIdentity,
        changeIdentity: review.changeIdentity,
        observedVaultRevision: review.observedVaultRevision,
        decision: state.intent as DecisionIntent,
        comment: state.comment,
        actorIdentifier: state.actorIdentifier,
        actorDisplayName: state.actorDisplayName,
        actorSource: KNOWLEDGE_REVIEW_ACTOR_SOURCE
      });
      if (
        generation !== decisionGeneration ||
        get(selectedReviewId) !== review.reviewArtifactIdentity
      ) {
        return false;
      }
      const result: RealDecisionResult = Object.freeze({
        fixture: false,
        hardStop: true,
        duplicate: envelope.duplicate,
        vaultModified: false,
        persistence: false,
        publication: false,
        currentVaultRevision: envelope.current_vault_revision,
        decision: envelope.decision,
        messageKey: 'review.decision.real_hard_stop'
      });
      decisionResult.set(result);
      appendActivity(
        'DECISION_CREATED',
        'review.activity.decision_created',
        review.reviewArtifactIdentity
      );
      closeDecisionDialog();
      try {
        const snapshot = await client.snapshot();
        if (generation === decisionGeneration) reviewSnapshot.set(snapshot);
      } catch (snapshotError) {
        const normalizedSnapshotError = normalizeKnowledgeReviewError(snapshotError);
        appendActivity(
          'ERROR',
          'review.activity.snapshot_refresh_failed',
          review.reviewArtifactIdentity,
          normalizedSnapshotError.code
        );
      }
      return true;
    } catch (error) {
      if (generation !== decisionGeneration) return false;
      const normalized = normalizeKnowledgeReviewError(error);
      decisionDialog.update((current) => ({
        ...current,
        submitting: false,
        errorKey:
          normalized.code === 'policy_blocked'
            ? 'review.decision.policy_blocked'
            : 'review.decision.failed'
      }));
      appendActivity(
        'ERROR',
        'review.activity.error',
        review.reviewArtifactIdentity,
        normalized.code
      );
      return false;
    }
  }

  function handleDecisionDialogEscape(key: string): boolean {
    if (key !== 'Escape' || !get(decisionDialog).open || get(decisionDialog).submitting) {
      return false;
    }
    closeDecisionDialog();
    return true;
  }

  function setReviewQuery(query: string): void {
    reviewFilters.update((state) => ({ ...state, query: query.slice(0, 200) }));
  }

  function toggleReviewStatus(status: ReviewStatus): void {
    reviewFilters.update((state) => {
      const next = state.statuses.includes(status)
        ? state.statuses.filter((item) => item !== status)
        : [...state.statuses, status];
      return { ...state, statuses: Object.freeze(next) };
    });
  }

  function toggleReviewOperation(operation: ReviewOperation): void {
    reviewFilters.update((state) => {
      const next = state.operations.includes(operation)
        ? state.operations.filter((item) => item !== operation)
        : [...state.operations, operation];
      return { ...state, operations: Object.freeze(next) };
    });
  }

  function setReviewSort(sort: ReviewFilterState['sort']): void {
    reviewFilters.update((state) => ({ ...state, sort }));
  }

  function clearReviewFilters(): void {
    reviewFilters.set(INITIAL_FILTERS);
  }

  function resetReviewCenterStore(): void {
    listGeneration += 1;
    getGeneration += 1;
    decisionGeneration += 1;
    activitySequence = 0;
    listMetadata = { totalCount: 0, returnedCount: 0, truncated: false, nextOffset: null };
    reviewCenterState.set(INITIAL_REVIEW_CENTER_STATE);
    reviewQueue.set([]);
    selectedReviewId.set(null);
    selectedReview.set(null);
    reviewSnapshot.set(null);
    decisionDialog.set(INITIAL_DIALOG);
    decisionResult.set(null);
    reviewFilters.set(INITIAL_FILTERS);
    reviewActivity.set([]);
  }

  return {
    reviewCenterState,
    reviewQueue,
    filteredReviewQueue,
    selectedReviewId,
    selectedReview,
    reviewSnapshot,
    reviewDiagnostics,
    reviewFilters,
    reviewActivity,
    decisionDialog,
    decisionResult,
    fixtureDecisionResult,
    realDecisionResult,
    loadReviewCenter,
    refreshReviewCenter,
    retryReviewCenter,
    selectReview,
    moveReviewSelection,
    selectReviewBoundary,
    openDecisionDialog,
    closeDecisionDialog,
    setDecisionComment,
    setDecisionActorIdentifier,
    setDecisionActorDisplayName,
    confirmFixtureDecision,
    confirmDecision,
    handleDecisionDialogEscape,
    setReviewQuery,
    toggleReviewStatus,
    toggleReviewOperation,
    setReviewSort,
    clearReviewFilters,
    resetReviewCenterStore
  };
}


function reviewPaginationError(message: string): Readonly<{ code: string; message: string }> {
  return Object.freeze({
    code: 'invalid_payload',
    message: message.slice(0, 240)
  });
}

function filterAndSortQueue(
  queue: readonly ReviewQueueItem[],
  filters: ReviewFilterState
): readonly ReviewQueueItem[] {
  const query = filters.query.trim().toLowerCase();
  const filtered = queue.filter((item) => {
    if (filters.statuses.length > 0 && !filters.statuses.includes(item.status)) return false;
    if (filters.operations.length > 0 && !filters.operations.includes(item.operation)) return false;
    if (!query) return true;
    return [
      item.proposalId,
      item.reviewArtifactIdentity,
      item.changeIdentity ?? '',
      item.targetStableId,
      item.operation,
      item.status
    ].some((value) => value.toLowerCase().includes(query));
  });
  filtered.sort((left, right) => {
    if (filters.sort === 'STATUS_THEN_IDENTITY') {
      const statusDifference = STATUS_ORDER[left.status] - STATUS_ORDER[right.status];
      if (statusDifference !== 0) return statusDifference;
    }
    if (left.reviewArtifactIdentity < right.reviewArtifactIdentity) return -1;
    if (left.reviewArtifactIdentity > right.reviewArtifactIdentity) return 1;
    return 0;
  });
  return Object.freeze(filtered);
}

const productionReviewCenter = createReviewCenterController();

function isTransientReviewError(code: string): boolean {
  return ['busy', 'sidecar_shutdown', 'sidecar_unavailable', 'timeout'].includes(code);
}

export const reviewCenterState = productionReviewCenter.reviewCenterState;
export const reviewQueue = productionReviewCenter.reviewQueue;
export const filteredReviewQueue = productionReviewCenter.filteredReviewQueue;
export const selectedReviewId = productionReviewCenter.selectedReviewId;
export const selectedReview = productionReviewCenter.selectedReview;
export const reviewSnapshot = productionReviewCenter.reviewSnapshot;
export const reviewDiagnostics = productionReviewCenter.reviewDiagnostics;
export const reviewFilters = productionReviewCenter.reviewFilters;
export const reviewActivity = productionReviewCenter.reviewActivity;
export const decisionDialog = productionReviewCenter.decisionDialog;
export const decisionResult = productionReviewCenter.decisionResult;
export const fixtureDecisionResult = productionReviewCenter.fixtureDecisionResult;
export const realDecisionResult = productionReviewCenter.realDecisionResult;
export const loadReviewCenter = productionReviewCenter.loadReviewCenter;
export const refreshReviewCenter = productionReviewCenter.refreshReviewCenter;
export const retryReviewCenter = productionReviewCenter.retryReviewCenter;
export const selectReview = productionReviewCenter.selectReview;
export const moveReviewSelection = productionReviewCenter.moveReviewSelection;
export const selectReviewBoundary = productionReviewCenter.selectReviewBoundary;
export const openDecisionDialog = productionReviewCenter.openDecisionDialog;
export const closeDecisionDialog = productionReviewCenter.closeDecisionDialog;
export const setDecisionComment = productionReviewCenter.setDecisionComment;
export const setDecisionActorIdentifier = productionReviewCenter.setDecisionActorIdentifier;
export const setDecisionActorDisplayName = productionReviewCenter.setDecisionActorDisplayName;
export const confirmFixtureDecision = productionReviewCenter.confirmFixtureDecision;
export const confirmDecision = productionReviewCenter.confirmDecision;
export const handleDecisionDialogEscape = productionReviewCenter.handleDecisionDialogEscape;
export const setReviewQuery = productionReviewCenter.setReviewQuery;
export const toggleReviewStatus = productionReviewCenter.toggleReviewStatus;
export const toggleReviewOperation = productionReviewCenter.toggleReviewOperation;
export const setReviewSort = productionReviewCenter.setReviewSort;
export const clearReviewFilters = productionReviewCenter.clearReviewFilters;
export const resetReviewCenterStore = productionReviewCenter.resetReviewCenterStore;

export function cycleDialogFocusIndex(
  currentIndex: number,
  focusableCount: number,
  shiftKey: boolean
): number {
  if (!Number.isInteger(focusableCount) || focusableCount <= 0) return -1;
  const boundedCurrent = Number.isInteger(currentIndex) && currentIndex >= 0
    ? currentIndex % focusableCount
    : 0;
  return shiftKey
    ? (boundedCurrent - 1 + focusableCount) % focusableCount
    : (boundedCurrent + 1) % focusableCount;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/shellStore.ts (249 строк, 8108 байт)

````typescript
import { get, writable } from 'svelte/store';
import { inspectorSections, modeOptions, modelOptions } from '$lib/data/mockData';
import type { ChatMessageState, InspectorSection, MockMessage, ModeOption, ModelOption, ThemeMode } from '$lib/data/mockData';
import { loadUiPreferences, updateUiPreferences } from './uiPreferences';

export const MAX_DRAFT_LENGTH = 1200;
export const MAX_ASSISTANT_MESSAGE_LENGTH = 262_144;

export type WorkspaceMode = 'chat' | 'review' | 'setup';
export type SettingsSection = 'interface' | 'models' | 'observability' | 'about';

const DEFAULT_CONVERSATION = 'local-chat';
let messageCounter = 0;
const initialUiPreferences = loadUiPreferences();

function cloneMessages(): MockMessage[] {
  return [];
}

export const themeMode = writable<ThemeMode>(initialUiPreferences.theme);
export const activeWorkspace = writable<WorkspaceMode>('chat');
export const sidebarExpanded = writable(true);
export const inspectorVisible = writable(initialUiPreferences.diagnosticsPanel === 'open');
export const inspectorDrawerOpen = writable(initialUiPreferences.diagnosticsPanel === 'open');
export const settingsPanelOpen = writable(false);
export const settingsSection = writable<SettingsSection>('interface');
export const selectedConversationId = writable(DEFAULT_CONVERSATION);
export const selectedModel = writable<ModelOption>(modelOptions[0]);
export const selectedMode = writable<ModeOption>('Chat');
export const chatMessages = writable<MockMessage[]>(cloneMessages());
export const mockMessages = chatMessages;
export const composerDraft = writable('');
export const activeInspectorSection = writable<InspectorSection>(inspectorSections[0]);
export const toolsPopoverOpen = writable(false);
export const commandPaletteOpen = writable(false);

export type ModelSetupMode = 'external' | 'managed';
export const modelSetupDrawerOpen = writable(false);
export const modelSetupMode = writable<ModelSetupMode>('external');
export const modelConnected = writable(false);

export function setActiveWorkspace(workspace: WorkspaceMode): void {
  activeWorkspace.set(workspace);
  toolsPopoverOpen.set(false);
  closeCommandPalette();
  closeSettings();
  modelSetupDrawerOpen.set(false);
}

export function setThemeMode(mode: ThemeMode): void {
  if (mode !== 'system' && mode !== 'light' && mode !== 'dark') return;
  themeMode.set(mode);
  updateUiPreferences({ theme: mode });
}

export function openSettings(sectionOrEvent: SettingsSection | Event = 'interface'): void {
  const section = typeof sectionOrEvent === 'string' ? sectionOrEvent : 'interface';
  toolsPopoverOpen.set(false);
  modelSetupDrawerOpen.set(false);
  settingsSection.set(section);
  settingsPanelOpen.set(true);
}

export function closeSettings(): void {
  settingsPanelOpen.set(false);
  settingsSection.set('interface');
}

export function openCommandPalette(): void {
  commandPaletteOpen.set(true);
}

export function closeCommandPalette(): void {
  commandPaletteOpen.set(false);
}

export function setDiagnosticsPanelOpen(open: boolean): void {
  if (typeof open !== 'boolean') return;
  inspectorVisible.set(open);
  inspectorDrawerOpen.set(open);
  updateUiPreferences({ diagnosticsPanel: open ? 'open' : 'closed' });
}

export function closeDiagnosticsPanel(): void {
  setDiagnosticsPanelOpen(false);
}

export function setSelectedModel(model: ModelOption): void {
  if (modelOptions.includes(model)) selectedModel.set(model);
}

export function setSelectedMode(mode: ModeOption): void {
  if (modeOptions.includes(mode)) selectedMode.set(mode);
}

export function setSelectedConversation(id: string): void {
  selectedConversationId.set(id);
}

export function setComposerDraft(value: string): void {
  composerDraft.set(value.slice(0, MAX_DRAFT_LENGTH));
}

export function appendMockMessage(rawDraft: string): boolean {
  const bounded = rawDraft.slice(0, MAX_DRAFT_LENGTH);
  const body = bounded.trim();
  if (!body) return false;

  messageCounter += 1;
  mockMessages.update((messages) => [
    ...messages,
    {
      id: `mock-user-${messageCounter}`,
      role: 'user',
      body
    }
  ]);
  composerDraft.set('');
  return true;
}

export function appendAcceptedChatTurn(requestId: string, rawDraft: string): boolean {
  const bounded = rawDraft.slice(0, MAX_DRAFT_LENGTH);
  const body = bounded.trim();
  if (!body || !/^[0-9a-f]{24}$/.test(requestId)) return false;
  if (get(chatMessages).some((message) => message.requestId === requestId)) return false;

  messageCounter += 1;
  chatMessages.update((messages) => [
    ...messages,
    {
      id: `chat-user-${messageCounter}`,
      role: 'user',
      body,
      requestId
    },
    {
      id: `chat-assistant-${messageCounter}`,
      role: 'assistant',
      body: '',
      requestId,
      state: 'accepted'
    }
  ]);
  composerDraft.set('');
  return true;
}

export function appendAssistantChunk(requestId: string, chunk: string): boolean {
  if (!chunk || !/^[0-9a-f]{24}$/.test(requestId)) return false;
  let appended = false;
  chatMessages.update((messages) => messages.map((message) => {
    if (message.role !== 'assistant' || message.requestId !== requestId || isTerminalMessage(message.state)) return message;
    appended = true;
    return {
      ...message,
      body: `${message.body}${chunk}`.slice(0, MAX_ASSISTANT_MESSAGE_LENGTH),
      state: 'streaming'
    };
  }));
  return appended;
}

export function finalizeAssistantMessage(
  requestId: string,
  state: Exclude<ChatMessageState, 'accepted' | 'streaming'>,
  error?: string
): boolean {
  let finalized = false;
  chatMessages.update((messages) => messages.map((message) => {
    if (message.role !== 'assistant' || message.requestId !== requestId || isTerminalMessage(message.state)) return message;
    finalized = true;
    return { ...message, state, error: error?.slice(0, 240) };
  }));
  return finalized;
}

function isTerminalMessage(state: ChatMessageState | undefined): boolean {
  return state === 'completed' || state === 'cancelled' || state === 'timed_out' || state === 'failed';
}

export function sendComposerDraft(): boolean {
  return appendMockMessage(get(composerDraft));
}

export function setActiveInspectorSection(section: InspectorSection): void {
  if (inspectorSections.includes(section)) activeInspectorSection.set(section);
}

export function openModelSetup(mode: ModelSetupMode = 'external'): void {
  modelSetupMode.set(mode);
  modelSetupDrawerOpen.set(true);
}

export function closeModelSetup(): void {
  modelSetupDrawerOpen.set(false);
}

export function setModelConnected(connected: boolean): void {
  modelConnected.set(connected);
}

export function closePopovers(): void {
  toolsPopoverOpen.set(false);
  closeCommandPalette();
  closeSettings();
  if (get(inspectorVisible) || get(inspectorDrawerOpen)) closeDiagnosticsPanel();
  modelSetupDrawerOpen.set(false);
}

export function handleGlobalEscape(key: string): boolean {
  if (key !== 'Escape') return false;
  if (get(commandPaletteOpen)) {
    closeCommandPalette();
    return true;
  }
  const hadOpenSurface =
    get(settingsPanelOpen) ||
    get(toolsPopoverOpen) ||
    get(inspectorVisible) ||
    get(inspectorDrawerOpen) ||
    get(modelSetupDrawerOpen);
  if (!hadOpenSurface) return false;
  closePopovers();
  return true;
}

export function resetShellStores(): void {
  const preferences = loadUiPreferences();
  messageCounter = 0;
  themeMode.set(preferences.theme);
  activeWorkspace.set('chat');
  sidebarExpanded.set(true);
  inspectorVisible.set(preferences.diagnosticsPanel === 'open');
  inspectorDrawerOpen.set(preferences.diagnosticsPanel === 'open');
  settingsPanelOpen.set(false);
  settingsSection.set('interface');
  selectedConversationId.set(DEFAULT_CONVERSATION);
  selectedModel.set(modelOptions[0]);
  selectedMode.set('Chat');
  mockMessages.set(cloneMessages());
  composerDraft.set('');
  activeInspectorSection.set(inspectorSections[0]);
  toolsPopoverOpen.set(false);
  commandPaletteOpen.set(false);
  modelSetupDrawerOpen.set(false);
  modelSetupMode.set('external');
  modelConnected.set(false);
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/uiPreferences.ts (114 строк, 3203 байт)

````typescript
export const UI_PREFERENCES_KEY = 'localcomet.ui.preferences.v1';
export const LEGACY_LANGUAGE_KEY = 'localcomet.ui.language';

export type UiTheme = 'system' | 'light' | 'dark';
export type UiLocale = 'ru' | 'en';
export type DiagnosticsPanelPreference = 'open' | 'closed';

export interface UiPreferences {
  theme: UiTheme;
  locale: UiLocale;
  diagnosticsPanel: DiagnosticsPanelPreference;
}

export const DEFAULT_UI_PREFERENCES: Readonly<UiPreferences> = Object.freeze({
  theme: 'system',
  locale: 'ru',
  diagnosticsPanel: 'closed'
});

function defaultPreferences(): UiPreferences {
  return { ...DEFAULT_UI_PREFERENCES };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isTheme(value: unknown): value is UiTheme {
  return value === 'system' || value === 'light' || value === 'dark';
}

function isLocale(value: unknown): value is UiLocale {
  return value === 'ru' || value === 'en';
}

function isDiagnosticsPanel(value: unknown): value is DiagnosticsPanelPreference {
  return value === 'open' || value === 'closed';
}

function normalizePreferences(value: unknown): UiPreferences {
  const preferences = defaultPreferences();
  if (!isRecord(value)) return preferences;

  if (isTheme(value.theme)) preferences.theme = value.theme;
  if (isLocale(value.locale)) preferences.locale = value.locale;
  if (isDiagnosticsPanel(value.diagnosticsPanel)) {
    preferences.diagnosticsPanel = value.diagnosticsPanel;
  }
  return preferences;
}

function browserStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

function legacyLocale(storage: Storage): UiLocale | null {
  try {
    const value = storage.getItem(LEGACY_LANGUAGE_KEY);
    return isLocale(value) ? value : null;
  } catch {
    return null;
  }
}

export function loadUiPreferences(): UiPreferences {
  const storage = browserStorage();
  if (!storage) return defaultPreferences();

  let serialized: string | null;
  try {
    serialized = storage.getItem(UI_PREFERENCES_KEY);
  } catch {
    return defaultPreferences();
  }

  if (serialized === null) {
    const preferences = defaultPreferences();
    preferences.locale = legacyLocale(storage) ?? preferences.locale;
    return preferences;
  }

  try {
    return normalizePreferences(JSON.parse(serialized) as unknown);
  } catch {
    return defaultPreferences();
  }
}

export function updateUiPreferences(patch: Readonly<Partial<UiPreferences>>): UiPreferences {
  const preferences = loadUiPreferences();

  if (isRecord(patch)) {
    if (isTheme(patch.theme)) preferences.theme = patch.theme;
    if (isLocale(patch.locale)) preferences.locale = patch.locale;
    if (isDiagnosticsPanel(patch.diagnosticsPanel)) {
      preferences.diagnosticsPanel = patch.diagnosticsPanel;
    }
  }

  const storage = browserStorage();
  if (storage) {
    try {
      storage.setItem(UI_PREFERENCES_KEY, JSON.stringify(preferences));
    } catch {
      // Browser storage can be unavailable or full; the in-memory caller still succeeds.
    }
  }

  return preferences;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/types/controlPlane.ts (125 строк, 3762 байт)

````typescript
export type BridgeState = 'DISCONNECTED' | 'CONNECTING' | 'READY' | 'UNAVAILABLE' | 'ERROR';
export type SessionState = 'OPEN' | 'CLOSED';
export type ThreadState = 'ACTIVE' | 'CLOSED';
export type TurnState = 'CREATED' | 'RUNNING' | 'CANCELLING' | 'CANCELLED' | 'COMPLETED' | 'FAILED';
export type ItemState = 'STARTED' | 'STREAMING' | 'COMPLETED' | 'FAILED';
export type ItemKind =
  | 'user_message'
  | 'assistant_message'
  | 'reasoning'
  | 'status'
  | 'tool_proposal'
  | 'tool_result'
  | 'approval_request'
  | 'verification_result';
export type ControlPlaneEventMethod =
  | 'sidecar.status'
  | 'session.created'
  | 'session.closed'
  | 'thread.created'
  | 'turn.started'
  | 'turn.completed'
  | 'turn.cancelled'
  | 'turn.failed'
  | 'item.started'
  | 'item.delta'
  | 'item.completed'
  | 'model.turn.started'
  | 'model.output.delta'
  | 'model.turn.completed'
  | 'model.turn.cancelled'
  | 'model.turn.timed_out'
  | 'model.turn.failed';
export type MockTurnBehavior = 'complete' | 'pending_model' | 'wait_for_cancel';
export type CancelReason = 'user_requested' | 'window_closing' | 'timeout';

export interface ControlPlaneCounts {
  readonly sessions: number;
  readonly threads: number;
  readonly turns: number;
  readonly active_turns: number;
}

export interface ControlPlaneLimits {
  readonly maximum_sessions: number;
  readonly maximum_threads_per_session: number;
  readonly maximum_turns_per_thread: number;
  readonly maximum_prompt_characters: number;
  readonly maximum_events_per_request: number;
}

export interface BootstrapResponse {
  readonly control_plane_version: 'v6.84.6';
  readonly protocol: 'localcomet.ipc';
  readonly protocol_version: '1.0';
  readonly sidecar_runtime_version: 'v6.84.3';
  readonly capabilities: readonly string[];
  readonly limits: ControlPlaneLimits;
  readonly counts: ControlPlaneCounts;
  readonly persistence: false;
  readonly models_connected: false;
  readonly provider_registry_available: false;
  readonly harness_registry_available: false;
  readonly sidecar_ready?: boolean;
}

export interface SessionSummary {
  readonly session_id: string;
  readonly state: SessionState;
  readonly title: string;
  readonly thread_count: number;
}

export interface ThreadSummary {
  readonly thread_id: string;
  readonly session_id: string;
  readonly state: ThreadState;
  readonly title: string;
  readonly turn_count: number;
  readonly active_turn_id: string | null;
}

export interface TurnSummary {
  readonly turn_id: string;
  readonly thread_id?: string;
  readonly state: TurnState;
  readonly prompt_sha256?: string;
  readonly prompt_preview?: string;
  readonly prompt_character_count?: number;
  readonly item_count?: number;
  readonly last_sequence?: number;
  readonly model_called: false;
  readonly tools_executed: 0;
  readonly events_emitted?: number;
  readonly waiting_for_cancel?: boolean;
  readonly waiting_for_decision?: boolean;
  readonly already_cancelled?: boolean;
  readonly already_terminal?: boolean;
}

export interface ControlPlaneEvent {
  readonly method: ControlPlaneEventMethod;
  readonly sequence: number;
  readonly reply_to: string;
  readonly control_plane_version: 'v6.84.6';
  readonly session_id: string | null;
  readonly thread_id: string | null;
  readonly turn_id: string | null;
  readonly item_id: string | null;
  readonly state: string;
  readonly kind: ItemKind | null;
  readonly text: string | null;
  readonly metadata: Readonly<Record<string, string | number | boolean | null>>;
}

export interface ControlPlaneItem {
  readonly item_id: string;
  readonly kind: ItemKind;
  readonly state: ItemState;
  readonly text: string;
}

export interface SanitizedBridgeError {
  readonly code: string;
  readonly message: string;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/types/files.ts (68 строк, 2103 байт)

````typescript
export const FILE_ID_PATTERN = /^[0-9a-f]{64}$/;

export type SelectedFileStatus = 'ready' | 'missing' | 'changed' | 'reparse_point' | 'unreadable';

export interface FilesCapabilityStatus {
  readonly available: boolean;
  readonly read_only: true;
  readonly selection: 'native_system_file_picker_only';
  readonly persistence: 'current_process_memory_only';
  readonly supported_extensions: readonly ['txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'];
  readonly maximum_file_bytes: number;
  readonly maximum_active_context_bytes: number;
  readonly maximum_selected_files: number;
  readonly preview_maximum_characters: number;
}

export interface SelectedFileSummary {
  readonly file_id: string;
  readonly filename: string;
  readonly extension: string;
  readonly media_type: string;
  readonly byte_size: number;
  readonly character_count: number;
  readonly readable: boolean;
  readonly status: SelectedFileStatus;
  readonly added_at_unix_ms: number;
  readonly display_location: string;
}

export interface FileSelectionResponse {
  readonly cancelled: boolean;
  readonly files: readonly SelectedFileSummary[];
}

export interface SelectedFilePreview {
  readonly file_id: string;
  readonly filename: string;
  readonly content: string;
  readonly original_bytes: number;
  readonly original_characters: number;
  readonly displayed_bytes: number;
  readonly displayed_characters: number;
  readonly truncated: boolean;
}

export interface FileCapabilityError {
  readonly code: string;
  readonly message: string;
}

export interface FileContextInclusion {
  readonly file_id: string;
  readonly filename: string;
  readonly original_bytes: number;
  readonly original_characters: number;
  readonly included_bytes: number;
  readonly included_characters: number;
  readonly inclusion: 'full' | 'bounded_excerpt';
}

export interface FilesContextReport {
  readonly source_bytes: number;
  readonly source_characters: number;
  readonly included_bytes: number;
  readonly included_characters: number;
  readonly truncated: boolean;
  readonly files: readonly FileContextInclusion[];
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/types/knowledgeReview.ts (584 строк, 19940 байт)

````typescript
export type ReviewStatus = 'CLEAR' | 'REVIEW_REQUIRED' | 'BLOCKED';
export type ConflictSeverity = 'BLOCKING' | 'REVIEW';
export type DecisionIntent = 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES';
export type ReviewOperation =
  | 'UPDATE_EXISTING'
  | 'CREATE_NEW'
  | 'DELETE'
  | 'MOVE'
  | 'RENAME'
  | 'SUPERSEDE';
export type ReviewSource = 'FIXTURE' | 'LOCAL_CONTROL_PLANE';
export type ReviewCenterLoadStatus = 'idle' | 'loading' | 'empty' | 'ready' | 'error';
export type ReviewFreshness = 'FRESH' | 'STALE' | 'UNKNOWN';
export type ReviewActivityKind =
  | 'INBOX_REFRESH'
  | 'ARTIFACT_OPENED'
  | 'STALE_REVIEW'
  | 'DECISION_CREATED'
  | 'ERROR'
  | 'SIDECAR_RECONNECT';

export interface BoundedTextPreviewProjection {
  readonly preview_text: string;
  readonly is_preview: boolean;
  readonly truncated: boolean;
  readonly original_utf8_bytes: number;
  readonly original_line_count: number;
  readonly preview_utf8_bytes: number;
  readonly preview_line_count: number;
}

export interface ProposedBodyProjection extends BoundedTextPreviewProjection {
  readonly raw_text_hash: string;
  readonly semantic_text_hash: string;
}

export interface BoundedStringCollectionProjection {
  readonly items: readonly string[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface ValidationMappingEntryProjection {
  readonly key: string;
  readonly value: ValidationValueProjection;
}

export interface ValidationValueProjection {
  readonly type_tag: 'mapping' | 'sequence' | 'null' | 'bool' | 'int' | 'string';
  readonly scalar_value: string | number | boolean | null;
  readonly mapping_items: readonly ValidationMappingEntryProjection[];
  readonly sequence_items: readonly ValidationValueProjection[];
}

export interface ValidationSnapshotProjection {
  readonly value: ValidationValueProjection;
  readonly truncated: boolean;
}

export interface SourceValidationFindingProjection {
  readonly code: string;
  readonly severity: string;
}

export interface BoundedSourceValidationFindingsProjection {
  readonly items: readonly SourceValidationFindingProjection[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface FindingDetailProjection {
  readonly key: string;
  readonly value: string;
}

export interface BoundedFindingDetailsProjection {
  readonly items: readonly FindingDetailProjection[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface ReviewFindingProjection {
  readonly code: string;
  readonly severity: ConflictSeverity;
  readonly message: BoundedTextPreviewProjection;
  readonly details: BoundedFindingDetailsProjection;
}

export interface BoundedReviewFindingsProjection {
  readonly items: readonly ReviewFindingProjection[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface LineEndingProfileProjection {
  readonly crlf_count: number;
  readonly lf_count: number;
  readonly cr_count: number;
  readonly terminal_newline: boolean;
}

export interface RepresentationDeltaProjection {
  readonly before_present: boolean;
  readonly after_present: boolean;
  readonly before_line_endings: LineEndingProfileProjection | null;
  readonly after_line_endings: LineEndingProfileProjection;
  readonly terminal_newline_changed: boolean;
  readonly after_source_bytes_known: boolean;
  readonly source_bytes_changed_text_identical: boolean;
  readonly raw_text_changed_semantic_equal: boolean;
  readonly semantic_content_changed: boolean;
  readonly identity: string;
}

export interface ProposedContentProjection {
  readonly title: string;
  readonly body_text: ProposedBodyProjection;
  readonly type: string;
  readonly status: string;
  readonly knowledge_layer: string;
  readonly evidence_class: string;
  readonly authority: string;
  readonly canonical: boolean;
  readonly canonical_scope: string | null;
  readonly aliases: BoundedStringCollectionProjection;
  readonly releases: BoundedStringCollectionProjection;
  readonly source_paths: BoundedStringCollectionProjection;
  readonly evidence_refs: BoundedStringCollectionProjection;
  readonly supersedes: BoundedStringCollectionProjection;
  readonly superseded_by: BoundedStringCollectionProjection;
  readonly updated: string;
  readonly last_reviewed: string;
  readonly verified_at: string | null;
}

export interface DiffProjection {
  readonly preview: BoundedTextPreviewProjection;
  readonly preview_truncated: boolean;
  readonly preview_is_full_diff: boolean;
  readonly full_diff_present: boolean;
  readonly full_diff_hash: string;
  readonly full_diff_utf8_bytes: number;
}

export interface KnowledgeChangeReviewProjection {
  readonly projection_contract: 'localcomet.knowledge-review-ui/1.0';
  readonly kind: 'KNOWLEDGE_CHANGE_REVIEW';
  readonly contract_version: string;
  readonly status: ReviewStatus;
  readonly proposal_id: string;
  readonly proposal_content_hash: string;
  readonly operation: ReviewOperation;
  readonly target_stable_id: string;
  readonly expected_vault_revision: string;
  readonly observed_vault_revision: string;
  readonly validation_outcome: 'VALID' | 'INVALID' | 'STALE';
  readonly validation_snapshot: ValidationSnapshotProjection;
  readonly source_validation_findings: BoundedSourceValidationFindingsProjection;
  readonly stable_id_set_hash: string;
  readonly proposed_content_snapshot: ProposedContentProjection;
  readonly findings: BoundedReviewFindingsProjection;
  readonly before_source_byte_hash: string | null;
  readonly before_text_raw_hash: string | null;
  readonly before_semantic_text_hash: string | null;
  readonly proposed_text_raw_hash: string;
  readonly proposed_semantic_text_hash: string;
  readonly diff: DiffProjection | null;
  readonly representation_delta: RepresentationDeltaProjection | null;
  readonly change_identity: string | null;
  readonly review_artifact_identity: string;
  readonly human_review_preview: BoundedTextPreviewProjection;
}

export interface KnowledgeReviewSummaryProjection {
  readonly projection_contract: 'localcomet.knowledge-review-ui/1.0';
  readonly kind: 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY';
  readonly contract_version: string;
  readonly status: ReviewStatus;
  readonly blocked: boolean;
  readonly proposal_id: string;
  readonly target_stable_id: string;
  readonly operation: ReviewOperation;
  readonly expected_vault_revision: string;
  readonly observed_vault_revision: string;
  readonly review_artifact_identity: string;
  readonly change_identity: string | null;
  readonly finding_count: number;
  readonly normal_change_material_present: boolean;
  readonly detail_projection_truncated: boolean;
}

export interface KnowledgeReviewListEnvelope {
  readonly contract: 'localcomet.knowledge-review-list/1.0';
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly offset: number;
  readonly limit: number;
  readonly total_count: number;
  readonly returned_count: number;
  readonly truncated: boolean;
  readonly next_offset: number | null;
  readonly items: readonly KnowledgeReviewSummaryProjection[];
}

export interface KnowledgeReviewGetEnvelope {
  readonly contract: 'localcomet.knowledge-review-get/1.0';
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly projection: KnowledgeChangeReviewProjection;
}

export interface KnowledgeReviewStateProjection {
  readonly review_artifact_identity: string;
  readonly status: ReviewStatus;
  readonly stale: boolean | null;
}

export interface KnowledgeReviewSnapshotEnvelope {
  readonly contract:
    | 'localcomet.knowledge-review-snapshot/1.0'
    | 'localcomet.knowledge-review-refresh/1.0';
  readonly command_center_version: 'v6.84.6';
  readonly control_plane_version: string;
  readonly sidecar_runtime_version: string;
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly refresh_requested: boolean;
  readonly refresh_succeeded: boolean;
  readonly current_vault_revision: string | null;
  readonly freshness_known: boolean;
  readonly knowledge_state: string;
  readonly last_error_code: string | null;
  readonly inbox_count: number;
  readonly stale_count: number;
  readonly blocked_count: number;
  readonly session_decision_count: number;
  readonly review_states: readonly KnowledgeReviewStateProjection[];
  readonly hard_stop: true;
  readonly persistence: false;
  readonly vault_write_authority: false;
  readonly publication_authority: false;
}

export interface HumanReviewerMetadataProjection {
  readonly actor_identifier: string;
  readonly display_name: string;
  readonly source: string;
}

export interface HumanReviewDecisionProjection {
  readonly projection_contract: 'localcomet.knowledge-review-ui/1.0';
  readonly kind: 'HUMAN_REVIEW_DECISION';
  readonly contract_version: 'localcomet.knowledge-change-review-decision/1.0';
  readonly review_contract_version: 'localcomet.knowledge-change-review/1.0';
  readonly review_status: ReviewStatus;
  readonly proposal_id: string;
  readonly review_artifact_identity: string;
  readonly change_identity: string | null;
  readonly observed_vault_revision: string;
  readonly decision: DecisionIntent;
  readonly comment: string;
  readonly actor: HumanReviewerMetadataProjection;
  readonly decision_identity: string;
  readonly hard_stop: true;
  readonly review_decision_only: true;
  readonly actor_metadata_evidence_only: true;
  readonly human_identity_authenticated: false;
  readonly grants_write_authority: false;
  readonly grants_vault_write_authority: false;
  readonly grants_persistence_authority: false;
  readonly grants_publication_authority: false;
  readonly grants_merge_authority: false;
  readonly grants_rebase_authority: false;
  readonly grants_execution_authority: false;
  readonly grants_policy_authority: false;
  readonly grants_model_gateway_authority: false;
  readonly grants_tauri_frontend_authority: false;
  readonly grants_automatic_approval_authority: false;
}

export interface KnowledgeReviewDecisionRequest {
  readonly reviewContractVersion: 'localcomet.knowledge-change-review/1.0';
  readonly proposalId: string;
  readonly reviewArtifactIdentity: string;
  readonly changeIdentity: string | null;
  readonly observedVaultRevision: string;
  readonly decision: DecisionIntent;
  readonly comment: string;
  readonly actorIdentifier: string;
  readonly actorDisplayName: string;
  readonly actorSource: 'LOCALCOMET_REVIEW_CENTER';
}

export interface KnowledgeReviewDecisionCreateEnvelope {
  readonly contract: 'localcomet.knowledge-review-decision-create/1.0';
  readonly command_center_version: 'v6.84.6';
  readonly control_plane_version: string;
  readonly sidecar_runtime_version: string;
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly duplicate: boolean;
  readonly current_vault_revision: string;
  readonly decision: HumanReviewDecisionProjection;
  readonly hard_stop: true;
  readonly vault_modified: false;
  readonly persistence: false;
  readonly publication: false;
}

export interface ReviewActivityEvent {
  readonly id: string;
  readonly sequence: number;
  readonly kind: ReviewActivityKind;
  readonly messageKey: string;
  readonly reviewArtifactIdentity: string | null;
  readonly errorCode: string | null;
}

export interface ReviewFilterState {
  readonly query: string;
  readonly statuses: readonly ReviewStatus[];
  readonly operations: readonly ReviewOperation[];
  readonly sort: 'IDENTITY_ASC' | 'STATUS_THEN_IDENTITY';
}

export interface ReviewDiagnostics {
  readonly commandCenterVersion: 'v6.84.6';
  readonly frontendContractVersion: 'localcomet.knowledge-review-ui/1.0';
  readonly tauriBridgeStatus: 'IDLE' | 'CONNECTING' | 'CONNECTED' | 'UNAVAILABLE' | 'ERROR';
  readonly sidecarConnectionState: 'IDLE' | 'CONNECTING' | 'CONNECTED' | 'UNAVAILABLE' | 'ERROR';
  readonly pythonRuntimeContractVersion: string | null;
  readonly inboxCount: number;
  readonly staleCount: number;
  readonly blockedCount: number;
  readonly sessionDecisionCount: number;
  readonly currentVaultRevision: string | null;
  readonly freshnessKnown: boolean;
  readonly lastErrorCode: string | null;
}

export interface ReviewQueueItem {
  readonly id: string;
  readonly fixture: boolean;
  readonly source: ReviewSource;
  readonly fixtureLabel?: string;
  readonly status: ReviewStatus;
  readonly blocked: boolean;
  readonly proposalId: string;
  readonly targetStableId: string;
  readonly operation: ReviewOperation;
  readonly expectedVaultRevision: string;
  readonly observedVaultRevision: string;
  readonly reviewArtifactIdentity: string;
  readonly changeIdentity: string | null;
  readonly findingCount: number;
  readonly normalChangeMaterialPresent: boolean;
  readonly detailProjectionTruncated: boolean;
  readonly stale: boolean | null;
}

export interface ReviewCenterError {
  readonly code: string;
  readonly message: string;
}

export interface ReviewCenterState {
  readonly status: ReviewCenterLoadStatus;
  readonly source: ReviewSource;
  readonly error: ReviewCenterError | null;
  readonly failedRequest: 'list' | 'get' | 'snapshot' | 'refresh' | 'decision' | null;
  readonly retryable: boolean;
  readonly totalCount: number;
  readonly returnedCount: number;
  readonly truncated: boolean;
  readonly nextOffset: number | null;
}

export const PROPOSED_CONTENT_FIELDS = [
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
] as const;

export type ProposedContentField = (typeof PROPOSED_CONTENT_FIELDS)[number];

export interface ProposedNoteContentView {
  readonly title: string;
  readonly body_text: string;
  readonly type: string;
  readonly status: string;
  readonly knowledge_layer: string;
  readonly evidence_class: string;
  readonly authority: string;
  readonly canonical: boolean;
  readonly canonical_scope: string | null;
  readonly aliases: readonly string[];
  readonly releases: readonly string[];
  readonly source_paths: readonly string[];
  readonly evidence_refs: readonly string[];
  readonly supersedes: readonly string[];
  readonly superseded_by: readonly string[];
  readonly updated: string;
  readonly last_reviewed: string;
  readonly verified_at: string | null;
}

export type MetadataValue = string | boolean | null | readonly string[];

export interface MetadataChange {
  readonly field: ProposedContentField;
  readonly before: MetadataValue;
  readonly after: MetadataValue;
}

export interface ReviewFinding {
  readonly code: string;
  readonly severity: ConflictSeverity;
  readonly message: string;
  readonly details: readonly (readonly [string, string])[];
}

export interface LineEndingProfileView {
  readonly label: 'NONE' | 'LF' | 'CRLF' | 'CR' | 'CRLF+LF' | 'CRLF+CR' | 'LF+CR' | 'CRLF+LF+CR';
  readonly crlfCount: number;
  readonly lfCount: number;
  readonly crCount: number;
  readonly terminalNewline: boolean;
}

export interface RepresentationDeltaView {
  readonly identity: string;
  readonly beforePresent: boolean;
  readonly afterPresent: boolean;
  readonly beforeLineEndings: LineEndingProfileView | null;
  readonly afterLineEndings: LineEndingProfileView;
  readonly terminalNewlineChanged: boolean;
  readonly afterSourceBytesKnown: boolean;
  readonly sourceBytesChangedTextIdentical: boolean;
  readonly rawTextChangedSemanticEqual: boolean;
  readonly semanticContentChanged: boolean;
}

export interface ValidationView {
  readonly outcome: 'VALID' | 'INVALID' | 'STALE';
  readonly contractVersion: string;
  readonly proposalContentHash: string;
  readonly validatedVaultRevision: string;
  readonly sourceFindings: readonly (readonly [string, string])[];
  readonly snapshotTruncated: boolean;
  readonly snapshotSummary: string;
}

export interface DiffPreviewView {
  readonly preview: string | null;
  readonly previewTruncated: boolean;
  readonly fullDiffAvailable: boolean;
  readonly fullDiffHash: string | null;
  readonly fullDiffUtf8Bytes: number | null;
}

export interface HumanReviewPreviewView {
  readonly text: string;
  readonly truncated: boolean;
}

interface ReviewCenterItemBase {
  readonly id: string;
  readonly status: ReviewStatus;
  readonly proposalId: string;
  readonly proposalContentHash: string;
  readonly reviewArtifactIdentity: string;
  readonly changeIdentity: string | null;
  readonly operation: ReviewOperation;
  readonly targetStableId: string;
  readonly expectedVaultRevision: string;
  readonly observedVaultRevision: string;
  readonly validation: ValidationView;
  readonly findings: readonly ReviewFinding[];
  readonly proposedContent: ProposedNoteContentView;
  readonly metadataChanges: readonly MetadataChange[];
  readonly beforeSourceByteHash: string | null;
  readonly beforeTextRawHash: string | null;
  readonly beforeSemanticTextHash: string | null;
  readonly proposedTextRawHash: string;
  readonly proposedSemanticTextHash: string;
  readonly textDiff: DiffPreviewView;
  readonly representationDelta: RepresentationDeltaView | null;
  readonly humanReviewPreview: HumanReviewPreviewView;
}

export interface FixtureReviewCenterItem extends ReviewCenterItemBase {
  readonly fixture: true;
  readonly source?: 'FIXTURE';
  readonly fixtureLabel: string;
  readonly detailProjectionTruncated?: false;
  readonly rawProjection?: never;
}

export interface RealReviewCenterItem extends ReviewCenterItemBase {
  readonly fixture: false;
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixtureLabel?: never;
  readonly detailProjectionTruncated: boolean;
  readonly stale: boolean | null;
  readonly rawProjection: KnowledgeChangeReviewProjection;
}

export type ReviewCenterItem = FixtureReviewCenterItem | RealReviewCenterItem;

export interface DecisionDialogState {
  readonly open: boolean;
  readonly intent: DecisionIntent | null;
  readonly comment: string;
  readonly actorIdentifier: string;
  readonly actorDisplayName: string;
  readonly submitting: boolean;
  readonly errorKey: string | null;
}

export interface FixtureDecisionResult {
  readonly fixture: true;
  readonly hardStop: true;
  readonly proposalId: string;
  readonly reviewArtifactIdentity: string;
  readonly intent: DecisionIntent;
  readonly comment: string;
  readonly messageKey: 'review.decision.fixture_hard_stop';
}

export interface RealDecisionResult {
  readonly fixture: false;
  readonly hardStop: true;
  readonly duplicate: boolean;
  readonly vaultModified: false;
  readonly persistence: false;
  readonly publication: false;
  readonly currentVaultRevision: string;
  readonly decision: HumanReviewDecisionProjection;
  readonly messageKey: 'review.decision.real_hard_stop';
}

export type ReviewDecisionResult = FixtureDecisionResult | RealDecisionResult;

export const CONFLICT_CODE_ORDER: Readonly<Record<string, number>> = Object.freeze({
  VALIDATION_RESULT_PROPOSAL_MISMATCH: 0,
  UNSUPPORTED_OPERATION: 1,
  STALE_VAULT_REVISION: 2,
  TARGET_MISSING: 3,
  UNVERIFIED_TEXT_INPUT: 4,
  TARGET_CHANGED_SINCE_PROPOSAL: 5,
  TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL: 6,
  TARGET_STATE_COMPARISON_UNAVAILABLE: 7,
  STABLE_ID_COLLISION: 8,
  PROPOSED_CONTENT_ALREADY_IDENTICAL: 9,
  PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT: 10
});

export function sortReviewFindings(findings: readonly ReviewFinding[]): readonly ReviewFinding[] {
  return [...findings].sort((left, right) => {
    const leftOrder = CONFLICT_CODE_ORDER[left.code] ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = CONFLICT_CODE_ORDER[right.code] ?? Number.MAX_SAFE_INTEGER;
    if (leftOrder !== rightOrder) return leftOrder - rightOrder;
    return left.code.localeCompare(right.code);
  });
}

export function isBlocked(review: ReviewCenterItem): boolean {
  return review.status === 'BLOCKED';
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/types/modelGateway.ts (328 строк, 10157 байт)

````typescript
export type ProviderId = 'openai-compatible-local' | 'managed-llama-cpp';
export type HarnessId = 'minimal' | 'native-localcomet';
export type AssistantLocale = 'ru' | 'en';
export type GatewayStatus =
  | 'Not configured'
  | 'Probing'
  | 'Unavailable'
  | 'Ready'
  | 'Binding required'
  | 'Bound'
  | 'Generating'
  | 'Cancelling'
  | 'Completed'
  | 'Cancelled'
  | 'Failed';

export type InferenceLifecycle =
  | 'idle'
  | 'submitted'
  | 'accepted'
  | 'streaming'
  | 'completed'
  | 'cancelling'
  | 'cancelled'
  | 'timed_out'
  | 'failed';

export interface GatewayCatalog {
  readonly gateway_version: 'v6.84.5';
  readonly providers: readonly { readonly provider_id: ProviderId; readonly label: string; readonly scheme: 'http' | 'internal'; readonly host: '127.0.0.1'; readonly base_path: '/v1' }[];
  readonly harnesses: readonly { readonly harness_id: HarnessId; readonly label: string }[];
  readonly persistence: false;
  readonly tools_available: false;
}

export interface ModelSummary {
  readonly model_id: string;
}

export interface ModelListResponse {
  readonly provider_id: ProviderId;
  readonly host: '127.0.0.1';
  readonly port: number;
  readonly models: readonly ModelSummary[];
  readonly discovered_fingerprint: string;
}

export interface ProbeResponse {
  readonly status: 'Ready';
  readonly provider_id: ProviderId;
  readonly host: '127.0.0.1';
  readonly port: number;
  readonly base_path: '/v1';
  readonly model_count: number;
}

export interface ModelBinding {
  readonly provider_id: ProviderId;
  readonly harness_id: HarnessId;
  readonly host?: '127.0.0.1';
  readonly port?: number;
  readonly base_path?: '/v1';
  readonly model_id: string;
  readonly binding_fingerprint: string;
  readonly discovered_fingerprint: string;
  readonly persistence: false;
  readonly runtime_instance_id?: string;
}

export interface ModelTurnStartResponse {
  readonly request_id: string;
  readonly chat_session_id: string;
  readonly turn_id: string;
  readonly state: 'Accepted';
  readonly model_id: string;
  readonly submitted_at_unix_ms: number;
  readonly max_tokens: number;
  readonly binding_fingerprint: string;
  readonly file_context?: import('./files').FilesContextReport;
}

export interface ModelTurnCancelResponse {
  readonly request_id: string;
  readonly turn_id: string;
  readonly state: 'Cancelling' | 'Cancelled';
  readonly accepted: boolean;
  readonly already_terminal: boolean;
  readonly worker_alive: boolean;
}

export type ModelEventMethod =
  | 'model.turn.started'
  | 'model.output.delta'
  | 'model.turn.completed'
  | 'model.turn.cancelled'
  | 'model.turn.timed_out'
  | 'model.turn.failed';

export interface ModelGatewayEvent {
  readonly method: ModelEventMethod;
  readonly sequence: number;
  readonly reply_to: string;
  readonly request_id: string;
  readonly chat_session_id: string;
  readonly turn_id: string;
  readonly state: 'Streaming' | 'Completed' | 'Cancelled' | 'TimedOut' | 'Failed';
  readonly text: string | null;
  readonly model_called: boolean;
  readonly tools_executed: 0;
  readonly persistence: false;
  readonly generated_bytes: number;
  readonly provider_id: ProviderId;
  readonly harness_id: HarnessId;
  readonly model_id: string;
  readonly binding_fingerprint: string;
  readonly error?: { readonly code: string; readonly message: string; readonly retryable: boolean };
}

export interface SanitizedGatewayError {
  readonly code: string;
  readonly message: string;
}

export type ManagedRuntimeState = 'NotInstalled' | 'Stopped' | 'Validating' | 'Starting' | 'Ready' | 'Stopping' | 'Failed';
export type ManagedModelState = 'Unavailable' | 'Validating' | 'Loading' | 'Ready' | 'Failed' | 'Unloading';

export interface ManagedRuntimeStatus {
  readonly engine: 'llama.cpp';
  readonly state: ManagedRuntimeState;
  readonly installation: 'Installed' | 'Not installed';
  readonly runtime_version: string | null;
  readonly runtime_instance_id: string | null;
  readonly runtime_instance_fingerprint: string | null;
  readonly model_id: string | null;
  readonly model_display_name: string | null;
  readonly binding_fingerprint: string | null;
  readonly model_state: ManagedModelState;
  readonly inference_ready: boolean;
  readonly last_error: string | null;
}

export interface InferenceRequestState {
  readonly lifecycle: InferenceLifecycle;
  readonly requestId: string | null;
  readonly chatSessionId: string | null;
  readonly modelId: string | null;
  readonly submittedAtUnixMs: number | null;
  readonly acceptedAtUnixMs: number | null;
  readonly firstTokenAtUnixMs: number | null;
  readonly terminalAtUnixMs: number | null;
  readonly maxTokens: number | null;
  readonly chunkCount: number;
  readonly nextSequence: number;
  readonly receivedContent: boolean;
  readonly cancellationAccepted: boolean;
  readonly terminalMethod: ModelEventMethod | null;
  readonly rejectedEventCount: number;
  readonly lastError: SanitizedGatewayError | null;
}

export type CatalogStatus = 'approved_internal_bootstrap';
export type ArtifactKind = 'runtime' | 'model';
export type ArtifactDownloadLifecycle =
  | 'idle'
  | 'awaiting_confirmation'
  | 'checking_disk'
  | 'downloading'
  | 'cancelling'
  | 'cancelled'
  | 'verifying_size'
  | 'verifying_hash'
  | 'validating_artifact'
  | 'installing'
  | 'completed'
  | 'failed';
export type ArtifactInstallationStatus =
  | 'not_installed'
  | 'valid'
  | 'bytes_mismatch'
  | 'hash_mismatch'
  | 'invalid_path'
  | 'invalid_format'
  | 'missing_required_file'
  | 'unexpected_file'
  | 'io_error';
export type CompatibilityStatus =
  | 'compatible'
  | 'no_compatible_runtime_installed'
  | 'incompatible_runtime_installed';
export type ManagedModelReadiness =
  | 'ready'
  | 'model_not_installed'
  | 'model_invalid'
  | 'runtime_not_installed'
  | 'runtime_invalid'
  | 'incompatible';

export interface ManagedCatalogIdentity {
  readonly schema_version: 1;
  readonly catalog_id: 'localcomet-approved-artifacts';
  readonly catalog_version: string;
  readonly catalog_digest: string;
}

export interface ApprovedRuntimeSummary {
  readonly runtime_id: string;
  readonly provider: string;
  readonly release_tag: string;
  readonly platform: 'windows';
  readonly architecture: 'x86-64';
  readonly variant: 'cpu';
  readonly upstream_repository: string;
  readonly upstream_revision: string;
  readonly asset_filename: string;
  readonly asset_bytes: number;
  readonly asset_sha256: string;
  readonly archive_format: 'zip';
  readonly permitted_bind_scope: 'loopback-only';
  readonly supported_api_protocol: 'openai-compatible-v1';
  readonly license_id: string;
  readonly public_distribution: false;
  readonly status: CatalogStatus;
}

export interface ApprovedModelSummary {
  readonly model_id: string;
  readonly provider: string;
  readonly family: string;
  readonly display_name: string;
  readonly format: 'GGUF';
  readonly quantization: 'Q4_K_M';
  readonly upstream_repository: string;
  readonly upstream_revision: string;
  readonly asset_filename: string;
  readonly asset_bytes: number;
  readonly asset_sha256: string;
  readonly license_id: string;
  readonly compatible_runtime_ids: readonly string[];
  readonly public_distribution: false;
  readonly installer_bundled: false;
  readonly bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION';
  readonly status: CatalogStatus;
}

export interface ManagedRuntimeCatalog extends ManagedCatalogIdentity {
  readonly runtimes: readonly ApprovedRuntimeSummary[];
}

export interface ManagedModelCatalog extends ManagedCatalogIdentity {
  readonly engine: 'llama.cpp';
  readonly model_root: '<MANAGED_MODEL_ROOT>';
  readonly models: readonly ApprovedModelSummary[];
  readonly maximum_models: 32;
}

export interface ArtifactValidationSummary extends ManagedCatalogIdentity {
  readonly artifact_id: string;
  readonly kind: ArtifactKind;
  readonly catalog_status: CatalogStatus;
  readonly installation_status: ArtifactInstallationStatus;
  readonly expected_bytes: number;
  readonly expected_sha256: string;
  readonly observed_bytes: number | null;
  readonly observed_sha256: string | null;
  readonly validation_code: string;
  readonly verified_unix_ms: number;
}

export interface ManagedInstalledArtifacts extends ManagedCatalogIdentity {
  readonly artifacts: readonly ArtifactValidationSummary[];
}

export interface ApprovedDownloadableArtifact {
  readonly artifact_id: string;
  readonly kind: ArtifactKind;
  readonly display_name: string;
  readonly source_identity: string;
  readonly expected_bytes: number;
  readonly license_id: string;
  readonly format: string | null;
  readonly quantization: string | null;
  readonly user_confirmation_required: true;
  readonly automatic_download: false;
}

export interface ArtifactDownloadState {
  readonly job_id: string;
  readonly artifact_id: string;
  readonly lifecycle: ArtifactDownloadLifecycle;
  readonly expected_bytes: number;
  readonly received_bytes: number;
  readonly percent: number | null;
  readonly started_utc_ms: number;
  readonly updated_utc_ms: number;
  readonly error_code: string | null;
}

export interface ManagedModelRemovalResult {
  readonly model_id: string;
  readonly removed: true;
}

export interface ModelReadinessSummary extends ManagedCatalogIdentity {
  readonly model_id: string;
  readonly model_status: ArtifactInstallationStatus;
  readonly compatible_runtime_ids: readonly string[];
  readonly selected_runtime_id: string | null;
  readonly runtime_status: ArtifactInstallationStatus | null;
  readonly compatibility: CompatibilityStatus;
  readonly readiness: ManagedModelReadiness;
  readonly launchable: boolean;
}

export interface ManagedRuntimeStartResponse {
  readonly state: 'Ready';
  readonly model_state: 'Ready';
  readonly inference_ready: true;
  readonly provider_id: 'managed-llama-cpp';
  readonly model_id: string;
  readonly model_display_name: string;
  readonly runtime_instance_id: string;
  readonly runtime_instance_fingerprint: string;
}

export interface ManagedRuntimeLogs {
  readonly stdout_tail: readonly string[];
  readonly stderr_tail: readonly string[];
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/version.ts (3 строк, 162 байт)

````typescript
export const DESKTOP_SHELL_VERSION = 'v6.84.5.1';
export const DESKTOP_BUILD_LABEL = 'v6.84.5.1b';
export const DESKTOP_BUILD_STATUS = 'UNSIGNED_INTERNAL_BUILD';
````

### ПУТЬ: desktop/localcomet-desktop/src/routes/+layout.ts (2 строк, 57 байт)

````typescript
export const ssr = false;
export const prerender = true;
````

### ПУТЬ: desktop/localcomet-desktop/src/routes/+page.svelte (5 строк, 107 байт)

````svelte
<script lang="ts">
  import AppShell from '$lib/components/shell/AppShell.svelte';
</script>

<AppShell />
````

### ПУТЬ: desktop/localcomet-desktop/svelte.config.js (17 строк, 371 байт)

````javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',
      strict: true
    })
  }
};

export default config;
````

### ПУТЬ: desktop/localcomet-desktop/tests/assistant-usability.test.ts (126 строк, 7371 байт)

````typescript
import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import MessageList from '../src/lib/components/chat/MessageList.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { setLocale } from '../src/lib/i18n';
import { managedRuntimeStore, modelGatewayStore, resetModelGatewayStore } from '../src/lib/stores/modelGateway';
import { chatMessages, resetShellStores } from '../src/lib/stores/shellStore';

const MODEL_ID = 'qwen2.5-1.5b-instruct-q4-k-m';
const RUNTIME_ID = 'llama-cpp-windows-x86-64-cpu-bootstrap';
const INSTANCE_ID = 'd'.repeat(32);
const FINGERPRINT = 'b'.repeat(64);
const CATALOG_DIGEST = 'c'.repeat(64);

function status(state: 'NotInstalled' | 'Starting' | 'Ready', modelState: 'Unavailable' | 'Loading' | 'Ready') {
  return {
    engine: 'llama.cpp' as const,
    state,
    installation: state === 'NotInstalled' ? 'Not installed' as const : 'Installed' as const,
    runtime_version: state === 'NotInstalled' ? null : 'b10068',
    runtime_instance_id: state === 'Ready' ? INSTANCE_ID : null,
    runtime_instance_fingerprint: state === 'Ready' ? 'e'.repeat(64) : null,
    model_id: state === 'Ready' ? MODEL_ID : null,
    model_display_name: state === 'Ready' ? 'Qwen2.5 1.5B Instruct Q4_K_M' : null,
    binding_fingerprint: state === 'Ready' ? 'f'.repeat(64) : null,
    model_state: modelState,
    inference_ready: state === 'Ready',
    last_error: null
  };
}

function seedReady(): void {
  const binding = {
    provider_id: 'managed-llama-cpp' as const,
    harness_id: 'minimal' as const,
    model_id: MODEL_ID,
    binding_fingerprint: FINGERPRINT,
    discovered_fingerprint: 'a'.repeat(64),
    persistence: false as const,
    runtime_instance_id: INSTANCE_ID
  };
  managedRuntimeStore.set({
    status: status('Ready', 'Ready'),
    catalogIdentity: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST },
    runtimeCatalog: [],
    catalog: [{ model_id: MODEL_ID, provider: 'Qwen', family: 'Qwen2.5', display_name: 'Qwen2.5 1.5B Instruct Q4_K_M', format: 'GGUF', quantization: 'Q4_K_M', upstream_repository: 'local', upstream_revision: 'revision', asset_filename: 'model.gguf', asset_bytes: 2, asset_sha256: '2'.repeat(64), license_id: 'apache-2.0', compatible_runtime_ids: [RUNTIME_ID], public_distribution: false, installer_bundled: false, bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION', status: 'approved_internal_bootstrap' }],
    installedArtifacts: [
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: RUNTIME_ID, kind: 'runtime', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 1, expected_sha256: '1'.repeat(64), observed_bytes: 1, observed_sha256: '1'.repeat(64), validation_code: 'valid', verified_unix_ms: 1 },
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: MODEL_ID, kind: 'model', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 2, expected_sha256: '2'.repeat(64), observed_bytes: 2, observed_sha256: '2'.repeat(64), validation_code: 'valid', verified_unix_ms: 1 }
    ],
    readiness: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, model_id: MODEL_ID, model_status: 'valid', compatible_runtime_ids: [RUNTIME_ID], selected_runtime_id: RUNTIME_ID, runtime_status: 'valid', compatibility: 'compatible', readiness: 'ready', launchable: true },
    selectedModelId: MODEL_ID,
    harnessId: 'minimal',
    binding,
    logs: { stdout_tail: [], stderr_tail: [] },
    lastError: null
  });
  modelGatewayStore.update((value) => ({ ...value, binding, status: 'Bound' }));
}

beforeEach(() => {
  resetModelGatewayStore();
  resetShellStores();
  setLocale('ru');
});

describe('truthful assistant usability states', () => {
  it('shows bounded unavailable guidance and the approved local setup action', () => {
    const html = render(MessageList).body;
    expect(html).toContain('Локальная модель недоступна');
    expect(html).toContain('нет доступа к интернету');
    expect(html).toContain('Настроить локальный AI');
  });

  it('shows loading without a false ready claim or send guidance', () => {
    managedRuntimeStore.update((value) => ({ ...value, status: status('Starting', 'Loading') }));
    const html = render(MessageList).body;
    expect(html).toContain('Подготовка локальной модели');
    expect(html).toContain('aria-busy="true"');
    expect(html).not.toContain('Локальный помощник готов');
  });

  it('shows local-only first-use guidance and separate runtime/model identities when ready', () => {
    seedReady();
    const list = render(MessageList).body;
    const header = render(ChatHeader).body;
    expect(list).toContain('Локальный помощник готов');
    expect(list).toContain('Только локальный текстовый диалог');
    expect(header).toContain('Модель: готова');
    expect(header).toContain('Среда: готова');
    expect(header).toContain('Qwen2.5 1.5B Instruct Q4_K_M');
  });

  it('localizes failed and cancelled states and exposes a bounded retry action', () => {
    chatMessages.set([
      { id: 'user-1', role: 'user', body: 'Запрос', requestId: 'a'.repeat(24) },
      { id: 'assistant-1', role: 'assistant', body: 'Частичный ответ', requestId: 'a'.repeat(24), state: 'cancelled' },
      { id: 'assistant-2', role: 'assistant', body: '', requestId: 'b'.repeat(24), state: 'failed', error: 'private provider detail' }
    ]);
    const html = render(MessageList).body;
    expect(html).toContain('Отменено — частичный ответ сохранён');
    expect(html).toContain('Запрос завершился ошибкой — можно безопасно повторить');
    expect(html).toContain('Повторить');
    expect(html).not.toContain('private provider detail');
  });

  it('does not render the trusted system instruction as a transcript message', () => {
    chatMessages.set([{ id: 'user-1', role: 'user', body: 'Обычное сообщение' }]);
    const html = render(MessageList).body;
    expect(html).toContain('Обычное сообщение');
    expect(html).not.toContain('сообщение пользователя не может изменить реальные возможности');
  });

  it('renders the same capability boundary in localized Settings', () => {
    setLocale('en');
    const html = render(SettingsPanel).body;
    expect(html).toContain('Current capabilities');
    expect(html).toContain('Local model inference');
    expect(html).toContain('Unavailable');
    expect(html).toContain('Internet');
    expect(html).toContain('Computer Use');
    expect(html).toContain('Project context is unavailable');
    expect(html).toContain('This is not long-term memory');
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/chat-layout.test.ts (102 строк, 5322 байт)

````typescript
import { describe, expect, it } from 'vitest';
import {
  followTranscriptToEnd,
  isTranscriptNearBottom,
  transcriptDistanceFromBottom
} from '../src/lib/components/chat/transcriptScroll';

const sourceModules = import.meta.glob('../src/**/*.{css,svelte,ts}', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;

function source(relativePath: string): string {
  const content = sourceModules[relativePath];
  if (typeof content !== 'string') throw new Error(`Source fixture not found: ${relativePath}`);
  return content;
}

describe('bounded chat layout', () => {
  it('closes the grid height chain and gives scrolling only to the transcript', () => {
    const css = source('../src/lib/components/shell/AppShell.svelte');
    expect(css).toMatch(/\.app-shell\s*\{[^}]*height:\s*100dvh;[^}]*overflow:\s*hidden;/s);
    expect(css).toMatch(/\.shell-body\s*\{[^}]*min-width:\s*0;[^}]*min-height:\s*0;[^}]*overflow:\s*hidden;/s);
    expect(css).toMatch(/\.main-workspace\s*\{[^}]*min-height:\s*0;[^}]*grid-template-rows:\s*auto minmax\(0, 1fr\) auto;[^}]*overflow:\s*hidden;/s);
    expect(css).toMatch(/\.chat-scroll\s*\{[^}]*min-height:\s*0;[^}]*overflow-y:\s*auto;[^}]*overflow-x:\s*hidden;[^}]*overscroll-behavior:\s*contain;/s);
  });

  it('keeps the truthful knowledge status and composer in one bounded footer grid item', () => {
    const composer = source('../src/lib/components/chat/MessageComposer.svelte');
    expect(composer).toContain('<div class="composer-region">');
    expect(composer).toMatch(/<div class="composer-region">\s*<form class="composer-wrap"/s);
    expect(composer).toContain('<KnowledgeToggle />');
    expect(composer).not.toContain('<KnowledgePreviewPanel />');
    expect(composer).toMatch(/\.composer-region\s*\{[^}]*min-width:\s*0;[^}]*min-height:\s*0;/s);
    expect(composer.match(/await restoreFocusAfterRequest\(\);/g)).toHaveLength(2);
    expect(composer).toContain('active === document.documentElement');
    expect(composer).toMatch(/if \(!textarea \|\| textarea\.disabled\) return;\s*restoreComposerFocus = false;/s);
    expect(composer).toMatch(/const generatingNow = isGenerating;\s*if \(previouslyGenerating && !generatingNow\)[\s\S]*previouslyGenerating = generatingNow;/);
  });

  it('keeps the owner-directed donor proportions and bubble geometry', () => {
    const messages = source('../src/lib/components/chat/MessageList.svelte');
    const composer = source('../src/lib/components/chat/MessageComposer.svelte');

    expect(messages).toMatch(/\.bubble\s*\{[^}]*max-width:\s*80%;[^}]*border-radius:\s*var\(--lc-radius-lg\);/s);
    expect(messages).toMatch(/\.user \.bubble\s*\{[^}]*background:\s*var\(--lc-accent\);/s);
    expect(composer).toMatch(/\.composer\s*\{[^}]*border-radius:\s*var\(--lc-radius-lg\);[^}]*box-shadow:\s*var\(--lc-shadow-e1\);/s);
  });

  it.each([
    ['1920×1080', 1920, 1080, 1],
    ['1366×768', 1366, 768, 1],
    ['1280×720', 1280, 720, 1],
    ['1024×640', 1024, 640, 1],
    ['125% equivalent', 1280, 720, 1.25],
    ['150% equivalent', 1024, 640, 1.5]
  ])('keeps a bounded positive transcript viewport at %s', (_name, width, height, scale) => {
    const titleBar = 48 * scale;
    const header = 48 * scale;
    const composer = 118 * scale;
    expect(width / scale).toBeGreaterThanOrEqual(682);
    expect(height - titleBar - header - composer).toBeGreaterThan(300);
  });

  it('makes the transcript keyboard-focusable and records manual scroll position', () => {
    const shell = source('../src/lib/components/shell/AppShell.svelte');
    expect(shell).toContain('bind:this={transcriptViewport}');
    expect(shell).toContain('tabindex="0"');
    expect(shell).toContain('onscroll={recordTranscriptPosition}');
    expect(shell).toContain('onkeydown={handleTranscriptKeydown}');
    expect(shell).toContain('isTranscriptNearBottom(transcriptViewport)');
    expect(shell).toContain("event.key === 'PageUp'");
    expect(shell).toContain("event.key === 'PageDown'");
    expect(shell).toContain("event.key === 'Home'");
    expect(shell).toContain("event.key === 'End'");
  });
});

describe('near-bottom transcript follow policy', () => {
  it('treats a one-message non-overflowing transcript as at bottom', () => {
    expect(isTranscriptNearBottom({ scrollTop: 0, clientHeight: 600, scrollHeight: 240 })).toBe(true);
  });

  it('follows a long or streaming transcript only near its bottom', () => {
    expect(isTranscriptNearBottom({ scrollTop: 2304, clientHeight: 600, scrollHeight: 3000 })).toBe(true);
    expect(isTranscriptNearBottom({ scrollTop: 1200, clientHeight: 600, scrollHeight: 3000 })).toBe(false);
  });

  it('does not mutate manual upward scrolling while tokens arrive', () => {
    const viewport = { scrollTop: 1200, clientHeight: 600, scrollHeight: 3100 };
    expect(followTranscriptToEnd(viewport, isTranscriptNearBottom(viewport))).toBe(false);
    expect(viewport.scrollTop).toBe(1200);
    expect(transcriptDistanceFromBottom(viewport)).toBe(1300);
  });

  it('resumes following after the user returns to the bottom', () => {
    const viewport = { scrollTop: 2500, clientHeight: 600, scrollHeight: 3100 };
    expect(followTranscriptToEnd(viewport, isTranscriptNearBottom(viewport))).toBe(true);
    expect(viewport.scrollTop).toBe(3100);
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/chat-reliability.test.ts (479 строк, 23175 байт)

````typescript
import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  INFERENCE_TIMEOUTS_MS,
  applyModelGatewayEvent,
  cancelLocalModelTurn,
  inferenceRequestStore,
  managedModelReady,
  managedRuntimeStore,
  modelGatewayStore,
  resetModelGatewayStore,
  retryLocalModelTurn,
  shutdownModelGateway,
  startLocalModelTurn
} from '../src/lib/stores/modelGateway';
import {
  chatMessages,
  composerDraft,
  resetShellStores,
  setComposerDraft
} from '../src/lib/stores/shellStore';
import { setLocale } from '../src/lib/i18n';
import type { ModelGatewayEvent } from '../src/lib/types/modelGateway';

const MODEL_ID = 'qwen2.5-1.5b-instruct-q4-k-m';
const RUNTIME_ID = 'llama-cpp-windows-x86-64-cpu-bootstrap';
const RUNTIME_INSTANCE_ID = 'd'.repeat(32);
const FINGERPRINT = 'b'.repeat(64);
const ATTACH_FINGERPRINT = 'f'.repeat(64);
const CATALOG_DIGEST = 'c'.repeat(64);

let listener: ((event: { payload: unknown }) => void) | null = null;
let listenCount = 0;
let cleanupCount = 0;
let invocationOrder: string[] = [];
let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let startHandler: (args: Record<string, unknown>) => Promise<unknown>;
let cancelHandler: (args: Record<string, unknown>) => Promise<unknown>;
let managedStatusHandler: () => Promise<unknown>;
let bindingHandler: (args: Record<string, unknown>) => Promise<unknown>;

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_channel: string, callback: (event: { payload: unknown }) => void) => {
    invocationOrder.push('listen');
    listenCount += 1;
    listener = callback;
    return () => {
      cleanupCount += 1;
      listener = null;
    };
  })
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>) => {
    invocationOrder.push(command);
    invokeCalls.push({ command, args });
    if (command === 'model_turn_start') return startHandler(args ?? {});
    if (command === 'model_turn_cancel') return cancelHandler(args ?? {});
    if (command === 'managed_runtime_status') return managedStatusHandler();
    if (command === 'model_binding_set') return bindingHandler(args ?? {});
    throw { code: 'unexpected_command', message: command };
  })
}));

function acceptance(args: Record<string, unknown>) {
  return {
    request_id: args.requestId,
    chat_session_id: args.chatSessionId,
    turn_id: args.requestId,
    state: 'Accepted',
    model_id: args.modelId,
    submitted_at_unix_ms: args.submittedAtUnixMs,
    max_tokens: args.maxTokens,
    binding_fingerprint: args.bindingFingerprint
  };
}

function cancellation(args: Record<string, unknown>, patch: Record<string, unknown> = {}) {
  return {
    request_id: args.requestId,
    turn_id: args.requestId,
    state: 'Cancelling',
    accepted: true,
    already_terminal: false,
    worker_alive: true,
    ...patch
  };
}

function seedReadyManagedModel(): void {
  const binding = {
    provider_id: 'managed-llama-cpp' as const,
    harness_id: 'minimal' as const,
    model_id: MODEL_ID,
    binding_fingerprint: FINGERPRINT,
    discovered_fingerprint: 'a'.repeat(64),
    persistence: false as const,
    runtime_instance_id: RUNTIME_INSTANCE_ID
  };
  managedRuntimeStore.set({
    status: {
      engine: 'llama.cpp',
      state: 'Ready',
      installation: 'Installed',
      runtime_version: 'b10068',
      runtime_instance_id: RUNTIME_INSTANCE_ID,
      runtime_instance_fingerprint: 'e'.repeat(64),
      model_id: MODEL_ID,
      model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      binding_fingerprint: ATTACH_FINGERPRINT,
      model_state: 'Ready',
      inference_ready: true,
      last_error: null
    },
    catalogIdentity: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST },
    runtimeCatalog: [],
    catalog: [{
      model_id: MODEL_ID,
      provider: 'Qwen',
      family: 'Qwen2.5',
      display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      format: 'GGUF',
      quantization: 'Q4_K_M',
      upstream_repository: 'https://example.invalid/model',
      upstream_revision: 'revision',
      asset_filename: 'model.gguf',
      asset_bytes: 2,
      asset_sha256: '2'.repeat(64),
      license_id: 'apache-2.0',
      compatible_runtime_ids: [RUNTIME_ID],
      public_distribution: false,
      installer_bundled: false,
      bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION',
      status: 'approved_internal_bootstrap'
    }],
    installedArtifacts: [
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: RUNTIME_ID, kind: 'runtime', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 1, expected_sha256: '1'.repeat(64), observed_bytes: null, observed_sha256: null, validation_code: 'valid', verified_unix_ms: 1 },
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: MODEL_ID, kind: 'model', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 2, expected_sha256: '2'.repeat(64), observed_bytes: 2, observed_sha256: '2'.repeat(64), validation_code: 'valid', verified_unix_ms: 1 }
    ],
    readiness: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, model_id: MODEL_ID, model_status: 'valid', compatible_runtime_ids: [RUNTIME_ID], selected_runtime_id: RUNTIME_ID, runtime_status: 'valid', compatibility: 'compatible', readiness: 'ready', launchable: true },
    selectedModelId: MODEL_ID,
    harnessId: 'minimal',
    binding,
    logs: { stdout_tail: [], stderr_tail: [] },
    lastError: null
  });
  modelGatewayStore.update((state) => ({ ...state, binding, status: 'Bound', lastError: null }));
}

function event(method: ModelGatewayEvent['method'], sequence: number, text: string | null = null, patch: Partial<ModelGatewayEvent> = {}): ModelGatewayEvent {
  const request = get(inferenceRequestStore);
  const stateByMethod = {
    'model.turn.started': 'Streaming',
    'model.output.delta': 'Streaming',
    'model.turn.completed': 'Completed',
    'model.turn.cancelled': 'Cancelled',
    'model.turn.timed_out': 'TimedOut',
    'model.turn.failed': 'Failed'
  } as const;
  return {
    method,
    sequence,
    reply_to: request.requestId!,
    request_id: request.requestId!,
    chat_session_id: request.chatSessionId!,
    turn_id: request.requestId!,
    state: stateByMethod[method],
    text,
    model_called: true,
    tools_executed: 0,
    persistence: false,
    generated_bytes: text?.length ?? 0,
    provider_id: 'managed-llama-cpp',
    harness_id: 'minimal',
    model_id: request.modelId!,
    binding_fingerprint: FINGERPRINT,
    ...patch
  };
}

async function startAccepted(prompt = 'hello'): Promise<string> {
  setComposerDraft(prompt);
  expect(await startLocalModelTurn(prompt, 'local-chat')).toBe(true);
  return get(inferenceRequestStore).requestId!;
}

beforeEach(() => {
  vi.useRealTimers();
  resetModelGatewayStore();
  resetShellStores();
  setLocale('ru');
  listener = null;
  listenCount = 0;
  cleanupCount = 0;
  invocationOrder = [];
  invokeCalls = [];
  startHandler = async (args) => acceptance(args);
  cancelHandler = async (args) => cancellation(args);
  seedReadyManagedModel();
  managedStatusHandler = async () => get(managedRuntimeStore).status;
  bindingHandler = async () => get(managedRuntimeStore).binding;
});

afterEach(() => {
  resetModelGatewayStore();
  resetShellStores();
  vi.useRealTimers();
});

describe('typed real-model chat lifecycle', () => {
  it('derives truthful readiness and never generates without it', async () => {
    expect(get(managedRuntimeStore).status?.binding_fingerprint).not.toBe(get(managedRuntimeStore).binding?.binding_fingerprint);
    expect(get(managedModelReady)).toBe(true);
    managedRuntimeStore.update((state) => ({ ...state, status: state.status ? { ...state.status, inference_ready: false } : null }));
    expect(get(managedModelReady)).toBe(false);
    setComposerDraft('keep this draft');
    expect(await startLocalModelTurn('keep this draft', 'local-chat')).toBe(false);
    expect(invokeCalls).toHaveLength(0);
    expect(get(composerDraft)).toBe('keep this draft');
    expect(get(chatMessages)).toHaveLength(0);
  });

  it('registers the listener before submit and sends the fixed typed request', async () => {
    await startAccepted();
    expect(invocationOrder).toEqual(['listen', 'managed_runtime_status', 'model_binding_set', 'model_turn_start']);
    const args = invokeCalls.find((call) => call.command === 'model_turn_start')?.args ?? {};
    expect(args.requestId).toMatch(/^[0-9a-f]{24}$/);
    expect(args).toMatchObject({ chatSessionId: 'local-chat', modelId: MODEL_ID, maxTokens: 256, prompt: 'hello', bindingFingerprint: FINGERPRINT });
    expect(get(composerDraft)).toBe('');
    expect(get(chatMessages).map((message) => message.role)).toEqual(['user', 'assistant']);
  });

  it('invalidates a stale binding before submission when the runtime has exited', async () => {
    managedStatusHandler = async () => ({
      ...get(managedRuntimeStore).status,
      state: 'Failed',
      model_state: 'Failed',
      inference_ready: false,
      last_error: 'managed runtime exited'
    });
    expect(await startLocalModelTurn('must not submit', 'local-chat')).toBe(false);
    expect(invokeCalls.some((call) => call.command === 'model_turn_start')).toBe(false);
    expect(get(managedModelReady)).toBe(false);
    expect(get(chatMessages)).toHaveLength(0);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'idle', lastError: { code: 'runtime_unavailable' } });
  });

  it('claims the submission gate before asynchronous preflight', async () => {
    let resolveStatus!: (value: unknown) => void;
    managedStatusHandler = () => new Promise((resolve) => {
      resolveStatus = resolve;
    });
    const first = startLocalModelTurn('first concurrent prompt', 'local-chat');
    await vi.waitFor(() => expect(invokeCalls.some((call) => call.command === 'managed_runtime_status')).toBe(true));
    expect(await startLocalModelTurn('second concurrent prompt', 'local-chat')).toBe(false);
    resolveStatus(get(managedRuntimeStore).status);
    expect(await first).toBe(true);
    expect(invokeCalls.filter((call) => call.command === 'model_turn_start')).toHaveLength(1);
  });

  it('buffers ordered events that arrive before acceptance and renders one assistant', async () => {
    let resolveStart!: (value: unknown) => void;
    startHandler = (args) => new Promise((resolve) => {
      resolveStart = () => resolve(acceptance(args));
    });
    setComposerDraft('race');
    const started = startLocalModelTurn('race', 'local-chat');
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('submitted'));
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'real '));
    applyModelGatewayEvent(event('model.output.delta', 2, 'answer'));
    applyModelGatewayEvent(event('model.turn.completed', 3));
    resolveStart(undefined);
    expect(await started).toBe(true);
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    expect(get(inferenceRequestStore)).toMatchObject({ chunkCount: 2 });
    expect(get(inferenceRequestStore).firstTokenAtUnixMs).not.toBeNull();
    expect(get(inferenceRequestStore).terminalAtUnixMs).not.toBeNull();
    expect(get(chatMessages).filter((message) => message.role === 'assistant')).toEqual([
      expect.objectContaining({ body: 'real answer', state: 'completed' })
    ]);
  });

  it('ignores foreign IDs and fails closed on a sequence gap', async () => {
    await startAccepted();
    const before = get(inferenceRequestStore);
    applyModelGatewayEvent(event('model.turn.started', 0, null, { request_id: 'f'.repeat(24), turn_id: 'f'.repeat(24), reply_to: 'f'.repeat(24) }));
    expect(get(inferenceRequestStore)).toEqual(before);
    applyModelGatewayEvent(event('model.output.delta', 1, 'gap'));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });
    expect(get(chatMessages).at(-1)).toMatchObject({ role: 'assistant', body: '', state: 'failed' });
  });

  it('rejects mismatched acceptance and event binding fingerprints', async () => {
    startHandler = async (args) => ({ ...acceptance(args), binding_fingerprint: '0'.repeat(64) });
    expect(await startLocalModelTurn('bad acceptance', 'local-chat')).toBe(false);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'invalid_payload' } });
    expect(get(chatMessages)).toHaveLength(0);

    startHandler = async (args) => acceptance(args);
    await startAccepted('bad event');
    applyModelGatewayEvent(event('model.turn.started', 0, null, { binding_fingerprint: '0'.repeat(64) }));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });
    expect(get(chatMessages).at(-1)).toMatchObject({ role: 'assistant', body: '', state: 'failed' });
    await vi.waitFor(() => expect(invokeCalls.filter((call) => call.command === 'model_turn_cancel')).toHaveLength(1));
  });

  it('rejects event provider and harness telemetry outside the active binding', async () => {
    await startAccepted('bad provider');
    applyModelGatewayEvent(event('model.turn.started', 0, null, { provider_id: 'openai-compatible-local' }));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });

    resetModelGatewayStore();
    resetShellStores();
    seedReadyManagedModel();
    await startAccepted('bad harness');
    applyModelGatewayEvent(event('model.turn.started', 0, null, { harness_id: 'native-localcomet' }));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });
  });

  it('snapshots the selected UI locale into the typed turn request', async () => {
    setLocale('en');
    await startAccepted('language context');
    expect(invokeCalls.find((call) => call.command === 'model_turn_start')?.args?.locale).toBe('en');
  });

  it('retries a terminal failed turn with a fresh isolated request', async () => {
    const firstId = await startAccepted('retry this request');
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.turn.failed', 1, null, { error: { code: 'model_request_failed', message: 'safe failure', retryable: true } }));
    expect(get(chatMessages).at(-1)).toMatchObject({ requestId: firstId, state: 'failed' });
    expect(await retryLocalModelTurn(firstId, 'local-chat')).toBe(true);
    const secondId = get(inferenceRequestStore).requestId;
    expect(secondId).not.toBe(firstId);
    expect(invokeCalls.filter((call) => call.command === 'model_turn_start')).toHaveLength(2);
  });

  it('rejects duplicate terminals and late tokens without changing finalized content', async () => {
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'done'));
    applyModelGatewayEvent(event('model.turn.completed', 2));
    const finalized = get(chatMessages);
    applyModelGatewayEvent(event('model.turn.completed', 3));
    applyModelGatewayEvent(event('model.output.delta', 4, ' late'));
    expect(get(chatMessages)).toEqual(finalized);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'completed', rejectedEventCount: 2 });
  });

  it('gives accepted cancellation precedence and ignores completion/late content', async () => {
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'partial'));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'cancelling', cancellationAccepted: true });
    applyModelGatewayEvent(event('model.turn.completed', 2));
    applyModelGatewayEvent(event('model.output.delta', 3, ' late'));
    applyModelGatewayEvent(event('model.turn.failed', 4, null, { error: { code: 'late_failure', message: 'late', retryable: false } }));
    applyModelGatewayEvent(event('model.turn.timed_out', 5, null, { error: { code: 'request_timed_out', message: 'late', retryable: true } }));
    applyModelGatewayEvent(event('model.turn.cancelled', 6));
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    expect(get(chatMessages).at(-1)).toMatchObject({ body: 'partial', state: 'cancelled' });
    expect(get(inferenceRequestStore).rejectedEventCount).toBe(3);
  });

  it('projects an accepted turn when Stop is pressed before acceptance resolves', async () => {
    let resolveStart!: (value?: unknown) => void;
    startHandler = (args) => new Promise((resolve) => {
      resolveStart = () => resolve(acceptance(args));
    });
    const pendingStart = startLocalModelTurn('cancel immediately', 'local-chat');
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('submitted'));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelling');

    resolveStart();
    expect(await pendingStart).toBe(true);
    expect(get(chatMessages).map((message) => message.role)).toEqual(['user', 'assistant']);
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelling');
    applyModelGatewayEvent(event('model.turn.cancelled', 0));
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    expect(get(chatMessages).at(-1)).toMatchObject({ body: '', state: 'cancelled' });
    expect(get(composerDraft)).toBe('');
  });

  it('settles cancellation when an unaccepted start rejects late', async () => {
    let rejectStart!: (reason?: unknown) => void;
    startHandler = () => new Promise((_resolve, reject) => {
      rejectStart = reject;
    });
    const pendingStart = startLocalModelTurn('cancel race', 'local-chat');
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('submitted'));
    await cancelLocalModelTurn();
    rejectStart({ code: 'request_not_found', message: 'late start response race' });
    expect(await pendingStart).toBe(false);
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    applyModelGatewayEvent(event('model.turn.cancelled', 0));
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    expect(get(chatMessages)).toHaveLength(0);
  });

  it('awaits the authoritative terminal when cancellation loses the terminal race', async () => {
    cancelHandler = async (args) => cancellation(args, { state: 'Cancelled', accepted: false, already_terminal: true, worker_alive: false });
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'won the race'));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'cancelling', cancellationAccepted: false });
    applyModelGatewayEvent(event('model.turn.completed', 2));
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    expect(get(chatMessages).at(-1)).toMatchObject({ body: 'won the race', state: 'completed' });
  });

  it('fails closed on an incoherent cancellation acknowledgement', async () => {
    cancelHandler = async (args) => cancellation(args, { state: 'Cancelled', accepted: true, already_terminal: false, worker_alive: true });
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'invalid_payload' } });
  });

  it('bounds acceptance, first-token and inactivity waits and remains retryable', async () => {
    vi.useFakeTimers();
    let resolveLate!: (value: unknown) => void;
    startHandler = (args) => new Promise((resolve) => {
      resolveLate = () => resolve(acceptance(args));
    });
    setComposerDraft('retry me');
    const pending = startLocalModelTurn('retry me', 'local-chat');
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.acceptance);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'request_acceptance_timeout' } });
    expect(get(composerDraft)).toBe('retry me');
    resolveLate(undefined);
    expect(await pending).toBe(false);

    startHandler = async (args) => acceptance(args);
    expect(await startLocalModelTurn('retry me', 'local-chat')).toBe(true);
    applyModelGatewayEvent(event('model.turn.started', 0));
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.firstToken);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'first_token_timeout' } });

    expect(await startLocalModelTurn('third', 'local-chat')).toBe(true);
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'partial'));
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.inactivity);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'stream_inactivity_timeout' } });
    expect(get(chatMessages).at(-1)).toMatchObject({ body: 'partial', state: 'timed_out' });
  });

  it('keeps second requests isolated and cleans/re-registers the listener', async () => {
    const firstId = await startAccepted('first');
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'one'));
    applyModelGatewayEvent(event('model.turn.completed', 2));
    shutdownModelGateway();
    expect(cleanupCount).toBe(1);

    const secondId = await startAccepted('second');
    expect(secondId).not.toBe(firstId);
    expect(listenCount).toBe(2);
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'two'));
    applyModelGatewayEvent(event('model.turn.completed', 2));
    applyModelGatewayEvent(event('model.output.delta', 3, 'old', { request_id: firstId, turn_id: firstId, reply_to: firstId }));
    expect(get(chatMessages).filter((message) => message.role === 'assistant').map((message) => message.body)).toEqual(['one', 'two']);
  });

  it('turns cancel acknowledgement timeout into one stable terminal', async () => {
    vi.useFakeTimers();
    cancelHandler = async () => new Promise(() => undefined);
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    const cancelling = cancelLocalModelTurn();
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.cancelAcknowledgement);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'cancel_ack_timeout' } });
    void cancelling;
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/componentSmoke.test.ts (93 строк, 4449 байт)

````typescript
import { render } from 'svelte/server';
import { describe, expect, it, beforeEach } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import ApprovalCard from '../src/lib/components/chat/ApprovalCard.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import ConversationSidebar from '../src/lib/components/shell/ConversationSidebar.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import NavigationRail from '../src/lib/components/shell/NavigationRail.svelte';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import ToolCallCard from '../src/lib/components/chat/ToolCallCard.svelte';
import { approvalCard, mockToolCall } from '../src/lib/data/mockData';
import { resetShellStores } from '../src/lib/stores/shellStore';

describe('component smoke tests', () => {
  beforeEach(() => {
    resetShellStores();
  });

  it('renders only functional minimal primary navigation', () => {
    const html = render(NavigationRail).body;
    expect(html).toContain('aria-label="Основная навигация"');
    expect(html).toContain('aria-label="Чат"');
    expect(html).toContain('aria-label="Настройки"');
    expect(html).not.toContain('Задачи');
    expect(html).not.toContain('позже');
    expect(html).not.toContain('Центр проверки');
    expect(html).toContain('LocalComet');
    expect(html).toContain('aria-current="page"');
  });

  it('renders functional sessions without placeholder or preference clutter', () => {
    const html = render(ConversationSidebar).body;
    expect(html).not.toContain('Зарезервировано');
    expect(html).not.toContain('Документы');
    expect(html).not.toContain('Новый тред');
    expect(html).not.toContain('Демо отмены');
    expect(html).not.toContain('v6.84.5.1b');
    expect(html).not.toContain('Frontend');
    expect(html).not.toContain('Использовать системную тему');
    expect(html).toContain('aria-expanded="true"');
  });

  it('renders the chat header with truthful runtime labels', () => {
    const html = render(ChatHeader).body;
    expect(html).toContain('Модель: недоступна');
    expect(html).toContain('Настроить локальный AI');
  });

  it('renders the tool card with sanitized target', () => {
    const html = render(ToolCallCard, { props: { tool: mockToolCall } }).body;
    expect(html).toContain('Инструменты');
    expect(html).toContain('Не настроено');
    expect(html).toContain('SKIPPED');
  });

  it('renders the disconnected approval card with disabled actions', () => {
    const html = render(ApprovalCard, { props: { item: approvalCard } }).body;
    expect(html).toContain('Подтверждения отключены');
    expect(html).toContain('disabled');
    expect(html).toContain('Подтвердить');
    expect(html).toContain('Отклонить');
  });

  it('renders useful Diagnostics without demo controls or no-op tabs', () => {
    const html = render(Diagnostics).body;
    expect(html).toContain('Провайдер');
    expect(html).toContain('Не настроено');
    expect(html).not.toContain('Запустить демо');
    expect(html).not.toContain('role="tablist"');
  });

  it('renders composer with an associated accessible label', () => {
    const html = render(MessageComposer).body;
    expect(html).toContain('for="composer-draft"');
    expect(html).toContain('id="composer-draft"');
    expect(html).toContain('aria-label="Введите сообщение…"');
    expect(html).toContain('Контекст проекта пока недоступен');
    expect(html).not.toContain('Инструменты (пока недоступны)');
    expect(html).not.toContain('request-metrics');
  });

  it('marks disabled approval buttons semantically', () => {
    const html = render(ApprovalCard, { props: { item: approvalCard } }).body;
    expect(html.match(/disabled/g)?.length).toBeGreaterThanOrEqual(2);
  });

  it('keeps theme controls accessible in Settings', () => {
    const html = render(SettingsPanel).body;
    expect(html).toContain('aria-label="Системная"');
    expect(html).toContain('title="Светлая"');
    expect(html).toContain('title="Тёмная"');
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/control-plane.test.ts (224 строк, 9792 байт)

````typescript
import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import {
  CONTROL_PLANE_EVENT_CHANNEL,
  bootstrapControlPlane,
  createSession,
  normalizeBridgeError,
  subscribeControlPlaneEvents
} from '../src/lib/bridge/controlPlane';
import {
  applyControlPlaneEvent,
  controlPlaneStore,
  initializeControlPlaneBridge,
  resetControlPlaneStore
} from '../src/lib/stores/controlPlane';
import type { ControlPlaneEvent } from '../src/lib/types/controlPlane';

const SESSION_ID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const THREAD_ID = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const TURN_ID = 'cccccccccccccccccccccccc';
const ITEM_ID = 'dddddddddddddddddddddddd';

let invokeCalls: string[] = [];
let listener: ((event: { payload: ControlPlaneEvent }) => void) | null = null;
let cleanupCalled = false;

const NO_BOOTSTRAP_OVERRIDE = Symbol('no-bootstrap-override');
const mockState: { failBootstrap: boolean; bootstrapOverride: unknown | typeof NO_BOOTSTRAP_OVERRIDE } = {
  failBootstrap: false,
  bootstrapOverride: NO_BOOTSTRAP_OVERRIDE
};

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string): Promise<unknown> => {
    invokeCalls.push(command);
    if (mockState.failBootstrap && command === 'control_plane_bootstrap') {
      throw { code: 'sidecar_unavailable', message: 'offline' };
    }
    if (command === 'control_plane_bootstrap') {
      return mockState.bootstrapOverride === NO_BOOTSTRAP_OVERRIDE ? bootstrapFixture() : mockState.bootstrapOverride;
    }
    if (command === 'control_plane_create_session') return { session_id: SESSION_ID, state: 'OPEN', title: 'Demo', thread_count: 0 };
    return {};
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_event: string, callback: (event: { payload: ControlPlaneEvent }) => void): Promise<() => void> => {
    listener = callback;
    return () => {
      cleanupCalled = true;
    };
  })
}));

function installTauriMock(
  failBootstrap = false,
  bootstrapOverride: unknown | typeof NO_BOOTSTRAP_OVERRIDE = NO_BOOTSTRAP_OVERRIDE
): void {
  invokeCalls = [];
  cleanupCalled = false;
  listener = null;
  mockState.failBootstrap = failBootstrap;
  mockState.bootstrapOverride = bootstrapOverride;
}

function bootstrapFixture() {
  return {
    control_plane_version: 'v6.84.6',
    protocol: 'localcomet.ipc',
    protocol_version: '1.0',
    sidecar_runtime_version: 'v6.84.3',
    capabilities: ['app.bootstrap', 'session.create', 'thread.create', 'turn.start_mock'],
    limits: {
      maximum_sessions: 16,
      maximum_threads_per_session: 32,
      maximum_turns_per_thread: 64,
      maximum_prompt_characters: 8192,
      maximum_events_per_request: 64
    },
    counts: { sessions: 0, threads: 0, turns: 0, active_turns: 0 },
    persistence: false,
    models_connected: false,
    provider_registry_available: false,
    harness_registry_available: false
  };
}

function event(method: ControlPlaneEvent['method'], sequence: number, patch: Partial<ControlPlaneEvent> = {}): ControlPlaneEvent {
  return {
    method,
    sequence,
    reply_to: patch.reply_to ?? 'deskcp-0000000001',
    control_plane_version: 'v6.84.6',
    session_id: patch.session_id ?? SESSION_ID,
    thread_id: patch.thread_id ?? THREAD_ID,
    turn_id: patch.turn_id ?? TURN_ID,
    item_id: patch.item_id ?? ITEM_ID,
    state: patch.state ?? '',
    kind: patch.kind ?? null,
    text: patch.text ?? null,
    metadata: patch.metadata ?? {}
  };
}

describe('control-plane bridge and store', () => {
  beforeEach(() => {
    resetControlPlaneStore();
    installTauriMock();
  });

  it('starts disconnected and reaches ready after one bootstrap', async () => {
    expect(get(controlPlaneStore).bridgeState).toBe('DISCONNECTED');
    const promise = initializeControlPlaneBridge();
    expect(get(controlPlaneStore).bridgeState).toBe('CONNECTING');
    await promise;
    expect(get(controlPlaneStore).bridgeState).toBe('READY');
    await initializeControlPlaneBridge();
    expect(invokeCalls.filter((command) => command === 'control_plane_bootstrap')).toHaveLength(1);
  });

  it('sets unavailable on bootstrap failure', async () => {
    installTauriMock(true);
    await initializeControlPlaneBridge();
    expect(get(controlPlaneStore).bridgeState).toBe('UNAVAILABLE');
  });

  it('accepts the authoritative Python Control Plane bootstrap version', async () => {
    const bootstrap = await bootstrapControlPlane();
    expect(bootstrap.control_plane_version).toBe('v6.84.6');
    expect(bootstrap.protocol_version).toBe('1.0');
    expect(bootstrap.sidecar_runtime_version).toBe('v6.84.3');
  });

  it('rejects the stale v6.84.4 bootstrap version', async () => {
    installTauriMock(false, { ...bootstrapFixture(), control_plane_version: 'v6.84.4' });
    await expect(bootstrapControlPlane()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('rejects malformed Control Plane bootstrap versions', async () => {
    for (const malformed of ['', '6.84.5.1', 'v6.84.5.1.0', null, 68451]) {
      installTauriMock(false, { ...bootstrapFixture(), control_plane_version: malformed });
      await expect(bootstrapControlPlane()).rejects.toMatchObject({ code: 'invalid_payload' });
    }
  });

  it('subscription returns cleanup and listener receives validated events', async () => {
    const seen: string[] = [];
    const cleanup = await subscribeControlPlaneEvents((payload) => seen.push(payload.method));
    listener?.({ payload: event('session.created', 0) });
    listener?.({ payload: event('model.turn.timed_out', 0, { reply_to: 'model-timeout', state: 'TimedOut' }) });
    cleanup();
    expect(cleanupCalled).toBe(true);
    expect(seen).toEqual(['session.created', 'model.turn.timed_out']);
  });

  it('accepts model timeout events in the shared Control Plane stream', () => {
    applyControlPlaneEvent(event('model.turn.timed_out', 0, { reply_to: 'model-timeout', state: 'TimedOut' }));
    const state = get(controlPlaneStore);
    expect(state.lastError).toBeNull();
    expect(state.recentEvents.at(-1)?.method).toBe('model.turn.timed_out');
  });

  it('updates session, thread, turn and items from ordered events', () => {
    applyControlPlaneEvent(event('session.created', 0, { reply_to: 'r1', metadata: { title: 'Demo' } }));
    applyControlPlaneEvent(event('thread.created', 0, { reply_to: 'r2', metadata: { title: 'Thread' } }));
    applyControlPlaneEvent(event('turn.started', 0, { reply_to: 'r3', state: 'RUNNING' }));
    applyControlPlaneEvent(event('item.started', 1, { reply_to: 'r3', kind: 'assistant_message', state: 'STARTED' }));
    applyControlPlaneEvent(event('item.delta', 2, { reply_to: 'r3', kind: 'assistant_message', state: 'STREAMING', text: 'No model ' }));
    applyControlPlaneEvent(event('item.completed', 3, { reply_to: 'r3', kind: 'assistant_message', state: 'COMPLETED' }));
    applyControlPlaneEvent(event('turn.completed', 4, { reply_to: 'r3', state: 'COMPLETED' }));
    const state = get(controlPlaneStore);
    expect(state.currentSession?.session_id).toBe(SESSION_ID);
    expect(state.currentThread?.thread_id).toBe(THREAD_ID);
    expect(state.currentTurn?.state).toBe('COMPLETED');
    expect(state.items[0]?.text).toContain('No model');
  });

  it('rejects duplicate and decreasing sequences and event after terminal', () => {
    applyControlPlaneEvent(event('turn.started', 0, { reply_to: 'r4', state: 'RUNNING' }));
    applyControlPlaneEvent(event('turn.completed', 1, { reply_to: 'r4', state: 'COMPLETED' }));
    applyControlPlaneEvent(event('item.delta', 2, { reply_to: 'r4', text: 'late' }));
    expect(get(controlPlaneStore).lastError?.code).toBe('invalid_sequence');
    applyControlPlaneEvent(event('item.delta', 1, { reply_to: 'r4', text: 'duplicate' }));
    expect(get(controlPlaneStore).lastError?.code).toBe('invalid_sequence');
  });

  it('keeps recent event and item lists bounded', () => {
    for (let index = 0; index < 140; index += 1) {
      applyControlPlaneEvent(event('item.started', index, { reply_to: 'bounded', item_id: `${index.toString(16).padStart(24, '0')}`, kind: 'status' }));
    }
    const state = get(controlPlaneStore);
    expect(state.recentEvents.length).toBeLessThanOrEqual(100);
    expect(state.items.length).toBeLessThanOrEqual(128);
  });

  it('does not persist or invent model/tool success', async () => {
    await createSession('x');
    expect(invokeCalls).toContain('control_plane_create_session');
    expect('localStorage' in globalThis).toBe(false);
    expect(get(controlPlaneStore).currentTurn?.model_called ?? false).toBe(false);
  });

  it('renders control plane status, demo notice and diagnostics facts', () => {
    const header = render(ChatHeader).body;
    const composer = render(MessageComposer).body;
    const diagnostics = render(Diagnostics).body;
    expect(header).toContain('Модель: недоступна');
    expect(composer).toContain('Сначала подключите модель');
    expect(diagnostics).toContain('Модель вызвана');
    expect(diagnostics).toContain('Инструментов выполнено');
    expect(diagnostics).toContain('Провайдер');
    expect(diagnostics).toContain('Не настроено');
  });

  it('normalizes errors and exposes no generic bridge method', () => {
    expect(normalizeBridgeError({ code: 'x', message: 'Traceback secret' }).message).toContain('<redacted>');
    expect(typeof bootstrapControlPlane).toBe('function');
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/diagnostics-localization.test.ts (224 строк, 8889 байт)

````typescript
import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import TelemetryRow from '../src/lib/components/common/TelemetryRow.svelte';
import { locale, setLocale, t } from '../src/lib/i18n';
import { controlPlaneStore, resetControlPlaneStore } from '../src/lib/stores/controlPlane';
import { modelGatewayStore, resetModelGatewayStore } from '../src/lib/stores/modelGateway';
import {
  activeInspectorSection,
  inspectorVisible,
  resetShellStores,
  setActiveInspectorSection
} from '../src/lib/stores/shellStore';

const diagnosticsSourceModules = import.meta.glob(
  [
    '../src/lib/components/agent/Diagnostics.svelte',
    '../src/lib/components/common/TelemetryRow.svelte',
    '../src/lib/components/common/EventStream.svelte'
  ],
  {
    eager: true,
    query: '?raw',
    import: 'default'
  }
) as Record<string, string>;

function diagnosticSource(relativePath: string): string {
  const content = diagnosticsSourceModules[relativePath];
  if (typeof content !== 'string') {
    throw new Error(`Diagnostics source fixture not found: ${relativePath}`);
  }
  return content;
}

function diagnosticsHtml(language: 'ru' | 'en'): string {
  setLocale(language);
  return render(Diagnostics).body;
}

beforeEach(() => {
  resetControlPlaneStore();
  resetModelGatewayStore();
  resetShellStores();
  locale.set('ru');
});

describe('Diagnostics localization closure', () => {
  it('keeps wrapped telemetry labels and values available as full titles', () => {
    const label = 'Long diagnostic label';
    const value = 'provider-with-a-very-long-local-identifier';
    const html = render(TelemetryRow, { props: { label, value, tone: 'info' } }).body;

    expect(html).toContain(`title="${label}"`);
    expect(html).toContain(`title="${value}"`);
  });

  it('keeps the bounded sticky-header and overflow source guards', () => {
    const diagnostics = diagnosticSource('../src/lib/components/agent/Diagnostics.svelte');
    const telemetryRow = diagnosticSource('../src/lib/components/common/TelemetryRow.svelte');
    const eventStream = diagnosticSource('../src/lib/components/common/EventStream.svelte');

    expect(diagnostics).toContain('position: sticky;');
    expect(diagnostics).toContain('overflow-x: hidden;');
    expect(diagnostics).toContain('--telemetry-row-columns: repeat(2, minmax(0, 1fr));');
    expect(diagnostics).toContain('min-width: 0;');
    expect(telemetryRow).toContain(
      'var(--telemetry-row-columns, minmax(0, 1fr) minmax(92px, auto))'
    );
    expect(telemetryRow).toContain('overflow-wrap: anywhere;');
    expect(eventStream).toContain('class="event-method" title={event.method}');
    expect(eventStream).toContain('overflow-wrap: anywhere;');
  });

  it('removes the known reachable English chrome from Russian Diagnostics', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    const html = diagnosticsHtml('ru');
    for (const gap of [
      'Runtime', 'Event Stream', 'No validated events received.', 'Policy Decision',
      'Not evaluated', 'Binding required', 'Off', 'Unavailable'
    ]) {
      expect(html).not.toContain(gap);
    }
  });

  it('renders the required English Diagnostics chrome', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    const html = diagnosticsHtml('en');
    for (const text of [
      'Runtime State', 'EVENT STREAM', 'No validated events received.', 'Binding required', 'Off'
    ]) {
      expect(html).toContain(text);
    }
    expect(html).not.toContain('POLICY DECISION');
    expect(html).not.toContain('Not evaluated');
  });

  it('translates Runtime State to Состояние системы', () => {
    expect(diagnosticsHtml('en')).toContain('Runtime State');
    expect(diagnosticsHtml('ru')).toContain('Состояние системы');
  });

  it('translates EVENT STREAM to ПОТОК СОБЫТИЙ', () => {
    expect(diagnosticsHtml('en')).toContain('EVENT STREAM');
    expect(diagnosticsHtml('ru')).toContain('ПОТОК СОБЫТИЙ');
  });

  it('localizes the empty event state', () => {
    expect(diagnosticsHtml('ru')).toContain('Проверенные события пока не получены.');
    expect(diagnosticsHtml('en')).toContain('No validated events received.');
  });

  it('does not render the unavailable policy placeholder', () => {
    expect(diagnosticsHtml('ru')).not.toContain('РЕШЕНИЕ ПОЛИТИКИ');
    expect(diagnosticsHtml('en')).not.toContain('POLICY DECISION');
  });

  it('does not render the placeholder not-evaluated status', () => {
    expect(diagnosticsHtml('ru')).not.toContain('Не оценивалось');
    expect(diagnosticsHtml('en')).not.toContain('Not evaluated');
  });

  it('localizes Binding required for display only', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    expect(diagnosticsHtml('ru')).toContain('Требуется подключение модели');
    expect(get(modelGatewayStore).status).toBe('Binding required');
  });

  it('localizes Off for display only', () => {
    expect(get(modelGatewayStore).persistence).toBe('Off');
    expect(diagnosticsHtml('ru')).toContain('Хранение данных');
    expect(diagnosticsHtml('ru')).not.toContain('>Off<');
    expect(get(modelGatewayStore).persistence).toBe('Off');
  });

  it('localizes Unavailable for display only', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Unavailable' }));
    expect(diagnosticsHtml('ru')).toContain('Недоступно');
    expect(get(modelGatewayStore).status).toBe('Unavailable');
  });

  it('keeps every reachable gateway runtime value unchanged internally', () => {
    const statuses = [
      'Not configured', 'Probing', 'Unavailable', 'Ready', 'Binding required', 'Bound',
      'Generating', 'Cancelling', 'Completed', 'Cancelled', 'Failed'
    ] as const;
    for (const status of statuses) {
      modelGatewayStore.update((state) => ({ ...state, status }));
      diagnosticsHtml('ru');
      expect(get(modelGatewayStore).status).toBe(status);
    }
  });

  it('preserves technical identifiers and raw event fields', () => {
    setLocale('ru');
    const translate = get(t);
    for (const identifier of [
      'LocalComet', 'llama.cpp', 'openai-compatible-local', 'managed-llama-cpp',
      'minimal', 'native-localcomet', 'model.turn.started', 'v6.84.5.1'
    ]) {
      expect(translate(identifier)).toBe(identifier);
    }
  });

  it('preserves the selected Diagnostics tab across locale switches', () => {
    setActiveInspectorSection('Телеметрия');
    setLocale('en');
    setLocale('ru');
    expect(get(activeInspectorSection)).toBe('Телеметрия');
  });

  it('does not reset Control Plane state on locale switch', () => {
    controlPlaneStore.update((state) => ({ ...state, bridgeState: 'ERROR' }));
    setLocale('en');
    setLocale('ru');
    expect(get(controlPlaneStore).bridgeState).toBe('ERROR');
  });

  it('does not reset Sidecar state on locale switch', () => {
    controlPlaneStore.update((state) => ({
      ...state,
      bootstrap: { sidecar_ready: true } as typeof state.bootstrap
    }));
    setLocale('en');
    setLocale('ru');
    expect(get(controlPlaneStore).bootstrap?.sidecar_ready).toBe(true);
  });

  it('keeps the event count unchanged on locale switch', () => {
    controlPlaneStore.update((state) => ({ ...state, eventCount: 7 }));
    setLocale('en');
    setLocale('ru');
    expect(get(controlPlaneStore).eventCount).toBe(7);
  });

  it('does not invent Ready or Connected state', () => {
    const html = diagnosticsHtml('en');
    expect(get(controlPlaneStore).bridgeState).toBe('DISCONNECTED');
    expect(get(controlPlaneStore).bootstrap).toBeNull();
    expect(html).not.toContain('Control Plane: Connected');
    expect(html).not.toContain('Sidecar: Ready');
  });

  it('keeps Diagnostics open while language changes', () => {
    inspectorVisible.set(true);
    setActiveInspectorSection('События');
    setLocale('en');
    expect(get(inspectorVisible)).toBe(true);
    expect(get(activeInspectorSection)).toBe('События');
    setLocale('ru');
    expect(get(inspectorVisible)).toBe(true);
    expect(get(activeInspectorSection)).toBe('События');
  });

  it('provides the required standalone Runtime and Connected translations', () => {
    setLocale('ru');
    expect(get(t)('diag.runtime')).toBe('Среда выполнения');
    expect(get(t)('diag.connected')).toBe('Подключено');
    setLocale('en');
    expect(get(t)('diag.runtime')).toBe('Runtime');
    expect(get(t)('diag.connected')).toBe('Connected');
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/files-capability.test.ts (247 строк, 9223 байт)

````typescript
import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FilesPanel from '../src/lib/components/files/FilesPanel.svelte';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { previewSelectedFile } from '../src/lib/bridge/files';
import {
  addFiles,
  filesStore,
  forgetFile,
  includedFilesTotals,
  initializeFilesCapability,
  openFilePreview,
  reportFilesContextInclusion,
  resetFilesStore,
  setFileIncluded
} from '../src/lib/stores/files';
import { setLocale } from '../src/lib/i18n';
import type { FilesCapabilityStatus, SelectedFileSummary } from '../src/lib/types/files';

const FILE_ID = 'a'.repeat(64);
const SECOND_FILE_ID = 'b'.repeat(64);
const CAPABILITY: FilesCapabilityStatus = {
  available: true,
  read_only: true,
  selection: 'native_system_file_picker_only',
  persistence: 'current_process_memory_only',
  supported_extensions: ['txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'],
  maximum_file_bytes: 2 * 1024 * 1024,
  maximum_active_context_bytes: 5 * 1024 * 1024,
  maximum_selected_files: 32,
  preview_maximum_characters: 16_000
};
const FILE: SelectedFileSummary = {
  file_id: FILE_ID,
  filename: 'notes.md',
  extension: 'md',
  media_type: 'Markdown',
  byte_size: 10,
  character_count: 10,
  readable: true,
  status: 'ready',
  added_at_unix_ms: 1_750_000_000_000,
  display_location: '…\\Temp\\notes.md'
};
const SECOND_FILE: SelectedFileSummary = {
  ...FILE,
  file_id: SECOND_FILE_ID,
  filename: 'data.json',
  extension: 'json',
  media_type: 'JSON',
  byte_size: 12,
  character_count: 12,
  display_location: '…\\Temp\\data.json'
};

let commands: Array<{ command: string; args?: Record<string, unknown> }> = [];
let selectedFiles: readonly SelectedFileSummary[] = [];
let selectionError: unknown = null;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    commands.push({ command, args });
    if (command === 'files_capability_status') return CAPABILITY;
    if (command === 'list_selected_files') return selectedFiles;
    if (command === 'select_files') {
      if (selectionError) throw selectionError;
      return { cancelled: false, files: selectedFiles };
    }
    if (command === 'preview_selected_file') {
      return {
        file_id: args?.fileId,
        filename: 'notes.md',
        content: '# Preview\n',
        original_bytes: 10,
        original_characters: 10,
        displayed_bytes: 10,
        displayed_characters: 10,
        truncated: false
      };
    }
    if (command === 'forget_selected_file') {
      selectedFiles = selectedFiles.filter((file) => file.file_id !== args?.fileId);
      return selectedFiles;
    }
    throw { code: 'unexpected_command', message: command };
  })
}));

const sourceModules = import.meta.glob('../src/lib/components/files/*.svelte', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;
const modelGatewayStoreSource = import.meta.glob('../src/lib/stores/modelGateway.ts', {
  eager: true,
  query: '?raw',
  import: 'default'
})['../src/lib/stores/modelGateway.ts'] as string;

beforeEach(() => {
  commands = [];
  selectedFiles = [];
  selectionError = null;
  resetFilesStore();
  setLocale('ru');
});

describe('Files capability frontend', () => {
  it('renders a truthful empty state without scanning or path controls', () => {
    installState([]);
    const html = render(FilesPanel).body;
    expect(html).toContain('Файлы не выбраны');
    expect(html).toContain('не сканирует диски и каталоги');
    expect(html).not.toMatch(/type="(?:text|file)"/);
  });

  it('selects through the fixed picker command and renders exact safe metadata', async () => {
    selectedFiles = [FILE];
    await initializeFilesCapability();
    await addFiles();
    const html = render(FilesPanel).body;
    expect(commands.map((entry) => entry.command)).toEqual(['files_capability_status', 'list_selected_files', 'select_files']);
    expect(commands.at(-1)?.args).toBeUndefined();
    expect(html).toContain('notes.md');
    expect(html).toContain('10 байт');
    expect(html).toContain('…\\Temp\\notes.md');
    expect(html).toContain('Читается');
  });

  it('shows the stable unsupported-type error without exposing backend detail', async () => {
    await initializeFilesCapability();
    selectionError = { code: 'LC_FILE_UNSUPPORTED_TYPE', message: 'backend detail' };
    await addFiles();
    expect(get(filesStore).lastError?.code).toBe('LC_FILE_UNSUPPORTED_TYPE');
    const html = render(FilesPanel).body;
    expect(html).toContain('Неподдерживаемый тип');
    expect(html).not.toContain('backend detail');
  });

  it('opens and renders a bounded preview with exact counters', async () => {
    selectedFiles = [FILE];
    await initializeFilesCapability();
    await openFilePreview(FILE_ID);
    expect(commands.at(-1)).toEqual({ command: 'preview_selected_file', args: { fileId: FILE_ID } });
    const html = render(FilesPanel).body;
    expect(html).toContain('# Preview');
    expect(html).toContain('10 / 10 байт');
    expect(html).toContain('role="dialog"');
  });

  it('requires explicit include and supports include/exclude toggling', () => {
    installState([FILE]);
    expect(get(filesStore).includedIds).toEqual([]);
    setFileIncluded(FILE_ID, true);
    expect(get(filesStore).includedIds).toEqual([FILE_ID]);
    setFileIncluded(FILE_ID, false);
    expect(get(filesStore).includedIds).toEqual([]);
  });

  it('shows exact aggregate source bytes and characters before send', () => {
    installState([FILE, SECOND_FILE]);
    setFileIncluded(FILE_ID, true);
    setFileIncluded(SECOND_FILE_ID, true);
    expect(get(includedFilesTotals)).toEqual({ bytes: 22, characters: 22, count: 2 });
    expect(render(FilesPanel).body).toContain('2 · 22 байт · 22 символов');
  });

  it('reports full versus bounded inclusion with visible exact counts', () => {
    installState([FILE]);
    reportFilesContextInclusion({
      source_bytes: 10,
      source_characters: 10,
      included_bytes: 5,
      included_characters: 5,
      truncated: true,
      files: [{
        file_id: FILE_ID,
        filename: 'notes.md',
        original_bytes: 10,
        original_characters: 10,
        included_bytes: 5,
        included_characters: 5,
        inclusion: 'bounded_excerpt'
      }]
    });
    const html = render(FilesPanel).body;
    expect(html).toContain('В последний запрос включён ограниченный фрагмент');
    expect(html).toContain('5 / 10 байт');
    expect(html).toContain('5 / 10 символов');
  });

  it('forget revokes inclusion, clears preview, and removes the file', async () => {
    selectedFiles = [FILE];
    await initializeFilesCapability();
    setFileIncluded(FILE_ID, true);
    await openFilePreview(FILE_ID);
    await forgetFile(FILE_ID);
    expect(commands.at(-1)).toEqual({ command: 'forget_selected_file', args: { fileId: FILE_ID } });
    expect(get(filesStore)).toMatchObject({ files: [], includedIds: [], preview: null });
  });

  it('derives Settings availability from backend capability status', () => {
    installState([]);
    const html = render(SettingsPanel).body;
    const available = html.slice(html.indexOf('Доступно'), html.indexOf('Недоступно'));
    const unavailable = html.slice(html.indexOf('Недоступно'));
    expect(available).toContain('Файлы');
    expect(unavailable).not.toContain('>Файлы<');
  });

  it('has labelled keyboard-operable controls and Escape preview handling', () => {
    const panel = sourceModules['../src/lib/components/files/FilesPanel.svelte'];
    const dialog = sourceModules['../src/lib/components/files/FilePreviewDialog.svelte'];
    expect(panel).toContain("aria-label={$t('files.add')}");
    expect(panel).toContain('type="checkbox"');
    expect(dialog).toContain("event.key === 'Escape'");
    expect(dialog).toContain('aria-modal="true"');
    expect(dialog).toContain("event.key !== 'Tab'");
  });

  it('rejects arbitrary path-like identities before invoking Tauri', async () => {
    await expect(previewSelectedFile('C:\\temp\\notes.md')).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(commands).toHaveLength(0);
  });

  it('never adds backend file context to the visible user chat transcript', () => {
    expect(modelGatewayStoreSource).toContain('appendAcceptedChatTurn(requestId, cleanPrompt)');
    expect(modelGatewayStoreSource).not.toContain('appendAcceptedChatTurn(requestId, acceptance.file_context');
    expect(modelGatewayStoreSource).not.toContain('appendAcceptedChatTurn(requestId, fileIds');
  });
});

function installState(files: readonly SelectedFileSummary[]): void {
  filesStore.set({
    initialized: true,
    capability: CAPABILITY,
    files,
    includedIds: [],
    preview: null,
    selecting: false,
    previewingId: null,
    forgettingId: null,
    lastError: null,
    lastContextReport: null
  });
}
````

### ПУТЬ: desktop/localcomet-desktop/tests/knowledge-preview.test.ts (121 строк, 11472 байт)

````typescript
import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KnowledgePreviewPanel from '../src/lib/components/knowledge/KnowledgePreviewPanel.svelte';
import KnowledgeSourceCard from '../src/lib/components/knowledge/KnowledgeSourceCard.svelte';
import KnowledgeToggle from '../src/lib/components/knowledge/KnowledgeToggle.svelte';
import { requestKnowledgePreview } from '../src/lib/bridge/knowledge';
import { locale, setLocale } from '../src/lib/i18n';
import type { KnowledgePreview, KnowledgePreviewSource } from '../src/lib/knowledge/knowledgePreview';
import {
  cancelProjectKnowledge,
  decideProjectKnowledge,
  knowledgePreviewStore,
  prepareProjectKnowledge,
  resetKnowledgePreviewStore,
  retryProjectKnowledgePreview,
  setProjectKnowledgeEnabled,
  toggleKnowledgeSource
} from '../src/lib/stores/knowledgePreview';

const TURN_ID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const CONTENT = 'Exact control plane section.';
const SOURCE: KnowledgePreviewSource = {
  note_id: 'architecture.control-plane',
  title: 'Control Plane boundary',
  relative_path: '01 Architecture/Control Plane.md',
  knowledge_layer: 'current_source_truth',
  evidence_class: 'A',
  authority: 'source',
  status: 'current',
  canonical: true,
  selected_sections: [{ heading: 'Boundary', line_start: 10, line_end: 12, content: CONTENT }]
};
const PREVIEW: KnowledgePreview = {
  state: 'PREVIEW_READY',
  turn_id: TURN_ID,
  request_id: 'kreq:00000000-0000-4000-8000-000000000001',
  injection_id: 'kinj:00000000-0000-4000-8000-000000000001',
  bundle_id: `kb:${'b'.repeat(64)}`,
  preview_hash: `sha256:${'c'.repeat(64)}`,
  vault_revision: `sha256:${'4'.repeat(64)}`,
  resolved_intent: 'AUTO',
  source_count: 1,
  total_chars: [...CONTENT].length,
  truncated: false,
  sources: [SOURCE],
  model_dispatched: false,
  tools_executed: 0
};

let commands: Array<{ command: string; args: Record<string, unknown> }> = [];
let response: unknown = PREVIEW;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args: Record<string, unknown>): Promise<unknown> => {
    commands.push({ command, args });
    if (command === 'knowledge_turn_decide') {
      return {
        state: args.action === 'CANCEL' || args.action === 'REJECT_AND_SEND_WITHOUT_KNOWLEDGE' ? 'REJECTED' : 'DISPATCHING',
        turn_id: TURN_ID,
        injection_id: PREVIEW.injection_id,
        decision_source: 'USER_APPROVAL',
        model_dispatched: args.action !== 'CANCEL'
      };
    }
    if (command === 'control_plane_cancel_turn') return { turn_id: TURN_ID, state: 'CANCELLED' };
    return response;
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async () => () => undefined)
}));

beforeEach(() => {
  commands = [];
  response = PREVIEW;
  resetKnowledgePreviewStore();
  locale.set('ru');
});

describe('desktop knowledge preview and approval', () => {
  it('01 defaults OFF', () => expect(get(knowledgePreviewStore).enabled).toBe(false));
  it('02 starts in OFF lifecycle', () => expect(get(knowledgePreviewStore).lifecycle).toBe('OFF'));
  it('03 production control is truthfully unavailable and non-interactive', () => {
    const html = render(KnowledgeToggle).body;
    expect(html).toContain('Контекст проекта пока недоступен');
    expect(html).toContain('Это не долговременная память');
    expect(html).not.toContain('role="switch"');
    expect(html).not.toContain('<button');
  });
  it('04 enabling is session state', () => { setProjectKnowledgeEnabled(true); expect(get(knowledgePreviewStore).enabled).toBe(true); });
  it('05 disabling clears preview identity', () => { setProjectKnowledgeEnabled(true); setProjectKnowledgeEnabled(false); expect(get(knowledgePreviewStore).turnId).toBeNull(); });
  it('06 OFF prepare performs no invoke', async () => { await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands).toHaveLength(0); });
  it('07 ON prepare invokes preview once', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands).toHaveLength(1); });
  it('08 preview uses exact bounded command', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands[0].command).toBe('knowledge_turn_preview'); });
  it('09 frontend payload has no query', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands[0].args).not.toHaveProperty('query'); });
  it('10 frontend payload has no vault path', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands[0].args).not.toHaveProperty('vaultRoot'); });
  it('11 preview reaches PREVIEW_READY', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).lifecycle).toBe('PREVIEW_READY'); });
  it('12 preview preserves injection identity', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).preview?.injection_id).toBe(PREVIEW.injection_id); });
  it('13 preview preserves source ordering', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).preview?.sources[0].note_id).toBe(SOURCE.note_id); });
  it('14 source card exposes provenance', () => { const html = render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: false, onToggle: () => undefined } }).body; expect(html).toContain(SOURCE.relative_path); });
  it('15 collapsed source hides exact content', () => { const html = render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: false, onToggle: () => undefined } }).body; expect(html).not.toContain(CONTENT); });
  it('16 expanded source shows exact content', () => { const html = render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: true, onToggle: () => undefined } }).body; expect(html).toContain(CONTENT); });
  it('17 expansion is local and causes no invoke', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); toggleKnowledgeSource(SOURCE.note_id); expect(commands).toHaveLength(0); });
  it('18 expansion preserves injection identity', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); toggleKnowledgeSource(SOURCE.note_id); expect(get(knowledgePreviewStore).preview?.injection_id).toBe(PREVIEW.injection_id); });
  it('19 locale switch causes no invoke', () => { setLocale('en'); expect(commands).toHaveLength(0); });
  it('20 locale switch preserves preview', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [SOURCE.note_id], lastError: null }); setLocale('en'); expect(get(knowledgePreviewStore).preview?.injection_id).toBe(PREVIEW.injection_id); });
  it('21 RU approval button complete', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); expect(render(KnowledgePreviewPanel).body).toContain('Включить знания и отправить'); });
  it('22 EN approval button complete', () => { setLocale('en'); knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); expect(render(KnowledgePreviewPanel).body).toContain('Include knowledge and send'); });
  it('23 include supplies no decision_source', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await decideProjectKnowledge('INCLUDE_AND_SEND'); expect(commands[0].args).not.toHaveProperty('decisionSource'); });
  it('24 include uses exact preview hash', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await decideProjectKnowledge('INCLUDE_AND_SEND'); expect(commands[0].args.expectedPreviewHash).toBe(PREVIEW.preview_hash); });
  it('25 include locks lifecycle while deciding', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await decideProjectKnowledge('INCLUDE_AND_SEND'); expect(get(knowledgePreviewStore).lifecycle).toBe('DISPATCHING'); });
  it('26 cancel uses bounded decide command and remains truthful', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await cancelProjectKnowledge(); expect(commands[0].args.action).toBe('CANCEL'); expect(get(knowledgePreviewStore).lifecycle).toBe('CANCELLED'); });
  it('27 retrieval failure never starts model', async () => { response = { state: 'FAILED', turn_id: TURN_ID, injection_id: null, error: { code: 'offline', safe_message: 'Unavailable' }, model_dispatched: false, tools_executed: 0 }; setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands.map((call) => call.command)).not.toContain('model_turn_start'); });
  it('28 retrieval failure is explicit FAILED', async () => { response = { state: 'FAILED', turn_id: TURN_ID, injection_id: null, error: { code: 'offline', safe_message: 'Unavailable' }, model_dispatched: false, tools_executed: 0 }; setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).lifecycle).toBe('FAILED'); });
  it('29 retry is explicit second preview call', async () => { response = { state: 'FAILED', turn_id: TURN_ID, injection_id: null, error: { code: 'offline', safe_message: 'Unavailable' }, model_dispatched: false, tools_executed: 0 }; setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); response = PREVIEW; await retryProjectKnowledgePreview(); expect(commands.filter((call) => call.command === 'knowledge_turn_preview')).toHaveLength(2); });
  it('30 malformed absolute path response fails closed', async () => { response = { ...PREVIEW, sources: [{ ...SOURCE, relative_path: 'C:/Vault/secret.md' }] }; await expect(requestKnowledgePreview({ turnId: TURN_ID, intent: 'AUTO', maxContextChars: 12000, maxResults: 8 })).rejects.toMatchObject({ code: 'invalid_payload' }); });
  it('31 malformed serialized wrapper response fails closed', async () => { response = { ...PREVIEW, serialized_context: 'secret' }; await expect(requestKnowledgePreview({ turnId: TURN_ID, intent: 'AUTO', maxContextChars: 12000, maxResults: 8 })).rejects.toMatchObject({ code: 'invalid_payload' }); });
  it('32 source cards are keyboard buttons', () => expect(render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: false, onToggle: () => undefined } }).body).toContain('<button'));
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/knowledge-review-bridge.test.ts (716 строк, 25020 байт)

````typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  MAX_KNOWLEDGE_REVIEW_LIST_LIMIT,
  createKnowledgeReviewDecision,
  getKnowledgeReview,
  getKnowledgeReviewSnapshot,
  listKnowledgeReviews,
  refreshKnowledgeReviews,
  reviewProjectionToCenterItem
} from '../src/lib/bridge/knowledgeReview';
import type {
  BoundedTextPreviewProjection,
  KnowledgeChangeReviewProjection,
  KnowledgeReviewDecisionCreateEnvelope,
  KnowledgeReviewDecisionRequest,
  KnowledgeReviewGetEnvelope,
  KnowledgeReviewListEnvelope,
  KnowledgeReviewSnapshotEnvelope,
  KnowledgeReviewSummaryProjection
} from '../src/lib/types/knowledgeReview';

const REVIEW_ID = `kreview:${'a'.repeat(64)}`;
const PROPOSAL_ID = `kprop:${'b'.repeat(64)}`;
const CHANGE_ID = `kchange:${'c'.repeat(64)}`;
const SHA_D = `sha256:${'d'.repeat(64)}`;
const SHA_E = `sha256:${'e'.repeat(64)}`;
const SHA_F = `sha256:${'f'.repeat(64)}`;
const bridgeMock = vi.hoisted(() => ({
  response: null as unknown,
  calls: [] as Array<{ command: string; args: Record<string, unknown> }>
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args: Record<string, unknown>): Promise<unknown> => {
    bridgeMock.calls.push({ command, args });
    return bridgeMock.response;
  })
}));

function lineCount(value: string): number {
  return value.length === 0 ? 0 : value.split(/\r\n|\r|\n/).length;
}

function text(value: string, truncated = false): BoundedTextPreviewProjection {
  const bytes = new TextEncoder().encode(value).length;
  const lines = lineCount(value);
  return {
    preview_text: value,
    is_preview: true,
    truncated,
    original_utf8_bytes: truncated ? bytes + 10 : bytes,
    original_line_count: truncated ? lines + 1 : lines,
    preview_utf8_bytes: bytes,
    preview_line_count: lines
  };
}

function summary(
  patch: Partial<KnowledgeReviewSummaryProjection> = {}
): KnowledgeReviewSummaryProjection {
  return {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status: 'REVIEW_REQUIRED',
    blocked: false,
    proposal_id: PROPOSAL_ID,
    target_stable_id: 'architecture.review-center',
    operation: 'UPDATE_EXISTING',
    expected_vault_revision: SHA_D,
    observed_vault_revision: SHA_E,
    review_artifact_identity: REVIEW_ID,
    change_identity: CHANGE_ID,
    finding_count: 1,
    normal_change_material_present: true,
    detail_projection_truncated: false,
    ...patch
  };
}

function listEnvelope(
  items: readonly KnowledgeReviewSummaryProjection[] = [summary()],
  patch: Partial<KnowledgeReviewListEnvelope> = {}
): KnowledgeReviewListEnvelope {
  return {
    contract: 'localcomet.knowledge-review-list/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    offset: 0,
    limit: 50,
    total_count: items.length,
    returned_count: items.length,
    truncated: false,
    next_offset: null,
    items,
    ...patch
  };
}

function projection(
  patch: Partial<KnowledgeChangeReviewProjection> = {}
): KnowledgeChangeReviewProjection {
  const body = 'Review Center body.\n';
  return {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status: 'REVIEW_REQUIRED',
    proposal_id: PROPOSAL_ID,
    proposal_content_hash: SHA_D,
    operation: 'UPDATE_EXISTING',
    target_stable_id: 'architecture.review-center',
    expected_vault_revision: SHA_D,
    observed_vault_revision: SHA_E,
    validation_outcome: 'VALID',
    validation_snapshot: {
      value: {
        type_tag: 'mapping',
        scalar_value: null,
        mapping_items: [
          {
            key: 'contract_version',
            value: {
              type_tag: 'string',
              scalar_value: 'localcomet.knowledge-change-review/1.0',
              mapping_items: [],
              sequence_items: []
            }
          },
          {
            key: 'proposal_content_hash',
            value: {
              type_tag: 'string',
              scalar_value: SHA_D,
              mapping_items: [],
              sequence_items: []
            }
          },
          {
            key: 'validated_vault_revision',
            value: {
              type_tag: 'string',
              scalar_value: SHA_E,
              mapping_items: [],
              sequence_items: []
            }
          }
        ],
        sequence_items: []
      },
      truncated: false
    },
    source_validation_findings: {
      items: [{ code: 'SOURCE_VALID', severity: 'INFO' }],
      original_count: 1,
      truncated: false
    },
    stable_id_set_hash: SHA_F,
    proposed_content_snapshot: {
      title: 'Review Center',
      body_text: {
        ...text(body),
        raw_text_hash: SHA_D,
        semantic_text_hash: SHA_E
      },
      type: 'architecture',
      status: 'current',
      knowledge_layer: 'current_source_truth',
      evidence_class: 'A',
      authority: 'source',
      canonical: true,
      canonical_scope: 'desktop',
      aliases: { items: ['review'], original_count: 1, truncated: false },
      releases: { items: ['v6.84.5.1'], original_count: 1, truncated: false },
      source_paths: {
        items: ['modules/knowledge_change_review_ru.py'],
        original_count: 1,
        truncated: false
      },
      evidence_refs: { items: ['e9b'], original_count: 1, truncated: false },
      supersedes: { items: [], original_count: 0, truncated: false },
      superseded_by: { items: [], original_count: 0, truncated: false },
      updated: '2026-07-16',
      last_reviewed: '2026-07-16',
      verified_at: null
    },
    findings: {
      items: [
        {
          code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
          severity: 'REVIEW',
          message: text('Comparison needs human review.'),
          details: {
            items: [{ key: 'target', value: 'architecture.review-center' }],
            original_count: 1,
            truncated: false
          }
        }
      ],
      original_count: 1,
      truncated: false
    },
    before_source_byte_hash: SHA_D,
    before_text_raw_hash: SHA_D,
    before_semantic_text_hash: SHA_E,
    proposed_text_raw_hash: SHA_D,
    proposed_semantic_text_hash: SHA_E,
    diff: {
      preview: text('@@ -1 +1 @@\n-old\n+new\n'),
      preview_truncated: false,
      preview_is_full_diff: false,
      full_diff_present: true,
      full_diff_hash: SHA_F,
      full_diff_utf8_bytes: 22
    },
    representation_delta: {
      before_present: true,
      after_present: true,
      before_line_endings: {
        crlf_count: 1,
        lf_count: 0,
        cr_count: 0,
        terminal_newline: true
      },
      after_line_endings: {
        crlf_count: 0,
        lf_count: 1,
        cr_count: 0,
        terminal_newline: true
      },
      terminal_newline_changed: false,
      after_source_bytes_known: true,
      source_bytes_changed_text_identical: false,
      raw_text_changed_semantic_equal: true,
      semantic_content_changed: false,
      identity: SHA_F
    },
    change_identity: CHANGE_ID,
    review_artifact_identity: REVIEW_ID,
    human_review_preview: text('Review this immutable proposal.'),
    ...patch
  };
}

function getEnvelope(
  value: KnowledgeChangeReviewProjection = projection(),
  patch: Partial<KnowledgeReviewGetEnvelope> = {}
): KnowledgeReviewGetEnvelope {
  return {
    contract: 'localcomet.knowledge-review-get/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    projection: value,
    ...patch
  };
}

function snapshotEnvelope(
  refreshRequested = false,
  patch: Partial<KnowledgeReviewSnapshotEnvelope> = {}
): KnowledgeReviewSnapshotEnvelope {
  return {
    contract: refreshRequested
      ? 'localcomet.knowledge-review-refresh/1.0'
      : 'localcomet.knowledge-review-snapshot/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.5.1e5',
    sidecar_runtime_version: 'v6.84.4.1',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    refresh_requested: refreshRequested,
    refresh_succeeded: refreshRequested,
    current_vault_revision: SHA_E,
    freshness_known: true,
    knowledge_state: 'READY',
    last_error_code: null,
    inbox_count: 1,
    stale_count: 0,
    blocked_count: 0,
    session_decision_count: 0,
    review_states: [
      {
        review_artifact_identity: REVIEW_ID,
        status: 'REVIEW_REQUIRED',
        stale: false
      }
    ],
    hard_stop: true,
    persistence: false,
    vault_write_authority: false,
    publication_authority: false,
    ...patch
  };
}

function decisionRequest(
  patch: Partial<KnowledgeReviewDecisionRequest> = {}
): KnowledgeReviewDecisionRequest {
  return {
    reviewContractVersion: 'localcomet.knowledge-change-review/1.0',
    proposalId: PROPOSAL_ID,
    reviewArtifactIdentity: REVIEW_ID,
    changeIdentity: CHANGE_ID,
    observedVaultRevision: SHA_E,
    decision: 'APPROVE',
    comment: '',
    actorIdentifier: 'local-user',
    actorDisplayName: 'Local user',
    actorSource: 'LOCALCOMET_REVIEW_CENTER',
    ...patch
  };
}

function decisionEnvelope(
  request: KnowledgeReviewDecisionRequest = decisionRequest(),
  patch: Partial<KnowledgeReviewDecisionCreateEnvelope> = {}
): KnowledgeReviewDecisionCreateEnvelope {
  return {
    contract: 'localcomet.knowledge-review-decision-create/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.5.1e5',
    sidecar_runtime_version: 'v6.84.4.1',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    duplicate: false,
    current_vault_revision: request.observedVaultRevision,
    decision: {
      projection_contract: 'localcomet.knowledge-review-ui/1.0',
      kind: 'HUMAN_REVIEW_DECISION',
      contract_version: 'localcomet.knowledge-change-review-decision/1.0',
      review_contract_version: request.reviewContractVersion,
      review_status: 'REVIEW_REQUIRED',
      proposal_id: request.proposalId,
      review_artifact_identity: request.reviewArtifactIdentity,
      change_identity: request.changeIdentity,
      observed_vault_revision: request.observedVaultRevision,
      decision: request.decision,
      comment: request.comment,
      actor: {
        actor_identifier: request.actorIdentifier,
        display_name: request.actorDisplayName,
        source: request.actorSource
      },
      decision_identity: `kdecision:${'1'.repeat(64)}`,
      hard_stop: true,
      review_decision_only: true,
      actor_metadata_evidence_only: true,
      human_identity_authenticated: false,
      grants_write_authority: false,
      grants_vault_write_authority: false,
      grants_persistence_authority: false,
      grants_publication_authority: false,
      grants_merge_authority: false,
      grants_rebase_authority: false,
      grants_execution_authority: false,
      grants_policy_authority: false,
      grants_model_gateway_authority: false,
      grants_tauri_frontend_authority: false,
      grants_automatic_approval_authority: false
    },
    hard_stop: true,
    vault_modified: false,
    persistence: false,
    publication: false,
    ...patch
  };
}

beforeEach(() => {
  bridgeMock.calls = [];
  bridgeMock.response = listEnvelope();
});

describe('fixed Knowledge Operations Command Center bridge', () => {
  it('invokes the exact bounded list command and freezes its accepted response', async () => {
    const result = await listKnowledgeReviews(0, 50);
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_list', args: { offset: 0, limit: 50 } }
    ]);
    expect(result.source).toBe('LOCAL_CONTROL_PLANE');
    expect(result.fixture).toBe(false);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.items)).toBe(true);
    expect(Object.isFrozen(result.items[0])).toBe(true);
  });

  it('accepts a truthful empty page at a bounded offset beyond the collection end', async () => {
    bridgeMock.response = listEnvelope([], {
      offset: 128,
      limit: 1,
      total_count: 0,
      returned_count: 0,
      truncated: false,
      next_offset: null
    });
    const result = await listKnowledgeReviews(128, 1);
    expect(result.items).toEqual([]);
    expect(result.offset).toBe(128);
    expect(result.total_count).toBe(0);
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_list', args: { offset: 128, limit: 1 } }
    ]);
  });

  it('invokes exact get, preserves all metadata, and retains the frozen raw projection', async () => {
    bridgeMock.response = getEnvelope();
    const result = await getKnowledgeReview(REVIEW_ID);
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_get', args: { reviewArtifactIdentity: REVIEW_ID } }
    ]);
    const item = reviewProjectionToCenterItem(result);
    expect(item.fixture).toBe(false);
    expect(item.source).toBe('LOCAL_CONTROL_PLANE');
    expect(item.rawProjection).toEqual(result.projection);
    expect(item.proposedContent.source_paths).toEqual(['modules/knowledge_change_review_ru.py']);
    expect(item.validation.proposalContentHash).toBe(SHA_D);
    expect(item.representationDelta?.beforeLineEndings?.label).toBe('CRLF');
    expect(item.representationDelta?.afterLineEndings.label).toBe('LF');
    expect(item.detailProjectionTruncated).toBe(false);
    expect(Object.isFrozen(item.rawProjection)).toBe(true);
  });

  it('preserves and aggregates bounded body, collection, finding-message, and detail facts', async () => {
    const base = projection();
    const baseFinding = base.findings.items[0];
    const boundedProjection = projection({
      proposed_content_snapshot: {
        ...base.proposed_content_snapshot,
        body_text: {
          ...base.proposed_content_snapshot.body_text,
          ...text('Bounded body preview.', true),
          raw_text_hash: SHA_D,
          semantic_text_hash: SHA_E
        },
        aliases: {
          items: ['review'],
          original_count: 2,
          truncated: true
        }
      },
      findings: {
        items: [
          {
            ...baseFinding,
            message: text('Bounded finding preview.', true),
            details: {
              items: [{ key: 'target', value: 'architecture.review-center' }],
              original_count: 2,
              truncated: true
            }
          }
        ],
        original_count: 2,
        truncated: true
      }
    });
    bridgeMock.response = getEnvelope(boundedProjection);

    const item = reviewProjectionToCenterItem(await getKnowledgeReview(REVIEW_ID));
    expect(item.detailProjectionTruncated).toBe(true);
    expect(item.rawProjection.proposed_content_snapshot.body_text.truncated).toBe(true);
    expect(item.rawProjection.proposed_content_snapshot.aliases.truncated).toBe(true);
    expect(item.rawProjection.findings.truncated).toBe(true);
    expect(item.rawProjection.findings.items[0].message.truncated).toBe(true);
    expect(item.rawProjection.findings.items[0].details.truncated).toBe(true);
  });

  it('accepts a safe source path within Python code-point and UTF-8 bounds', async () => {
    const unicodePath = Array.from({ length: 5 }, () => '😀'.repeat(60)).join('/');
    expect([...unicodePath].length).toBe(304);
    expect(new TextEncoder().encode(unicodePath).length).toBe(1_204);
    const base = projection();
    bridgeMock.response = getEnvelope(projection({
      proposed_content_snapshot: {
        ...base.proposed_content_snapshot,
        source_paths: {
          items: [unicodePath],
          original_count: 1,
          truncated: false
        }
      }
    }));

    const accepted = await getKnowledgeReview(REVIEW_ID);
    expect(accepted.projection.proposed_content_snapshot.source_paths.items).toEqual([unicodePath]);
  });

  it('rejects wrong list contract, projection kind, and malformed identities', async () => {
    bridgeMock.response = { ...listEnvelope(), contract: 'localcomet.wrong/1.0' };
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = listEnvelope([
      { ...summary(), kind: 'KNOWLEDGE_CHANGE_REVIEW' as never }
    ]);
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    await expect(getKnowledgeReview('kreview:not-a-hash')).rejects.toMatchObject({
      code: 'invalid_payload'
    });
  });

  it('rejects wrong full projection contract, kind, get identity, and unsafe source paths', async () => {
    bridgeMock.response = getEnvelope(
      projection({ projection_contract: 'localcomet.wrong/1.0' as never })
    );
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = getEnvelope(projection({ kind: 'HUMAN_REVIEW_DECISION' as never }));
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    const otherIdentity = `kreview:${'9'.repeat(64)}`;
    bridgeMock.response = getEnvelope(projection({ review_artifact_identity: otherIdentity }));
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = getEnvelope(
      projection({
        proposed_content_snapshot: {
          ...projection().proposed_content_snapshot,
          source_paths: {
            items: ['C:/Vault/secret.md'],
            original_count: 1,
            truncated: false
          }
        }
      })
    );
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('enforces offset, limit, response, and projection bounds before accepting data', async () => {
    await expect(listKnowledgeReviews(129, 1)).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(listKnowledgeReviews(0, 0)).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(listKnowledgeReviews(0, MAX_KNOWLEDGE_REVIEW_LIST_LIMIT + 1)).rejects.toMatchObject({
      code: 'invalid_payload'
    });
    expect(bridgeMock.calls).toHaveLength(0);

    bridgeMock.response = { padding: 'x'.repeat(1_048_576) };
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = getEnvelope(
      projection({
        human_review_preview: {
          ...text('x'),
          preview_text: 'x'.repeat(262_145),
          preview_utf8_bytes: 262_145,
          original_utf8_bytes: 262_145
        }
      })
    );
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('preserves BLOCKED absence and rejects synthesized normal change material', async () => {
    const blocked = projection({
      status: 'BLOCKED',
      diff: null,
      representation_delta: null,
      change_identity: null
    });
    bridgeMock.response = getEnvelope(blocked);
    const accepted = reviewProjectionToCenterItem(await getKnowledgeReview(REVIEW_ID));
    expect(accepted.changeIdentity).toBeNull();
    expect(accepted.textDiff.preview).toBeNull();
    expect(accepted.representationDelta).toBeNull();

    bridgeMock.response = getEnvelope({ ...blocked, diff: projection().diff });
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('rejects duplicate summaries and inconsistent continuation metadata', async () => {
    bridgeMock.response = listEnvelope([summary(), summary()], {
      total_count: 2,
      returned_count: 2
    });
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = listEnvelope([summary()], {
      total_count: 2,
      returned_count: 1,
      truncated: true,
      next_offset: null
    });
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('invokes exact snapshot and refresh commands with immutable freshness state', async () => {
    bridgeMock.response = snapshotEnvelope(false);
    const snapshot = await getKnowledgeReviewSnapshot();
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_snapshot', args: undefined }
    ]);
    expect(snapshot.review_states[0]).toMatchObject({
      review_artifact_identity: REVIEW_ID,
      stale: false
    });
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot.review_states)).toBe(true);

    bridgeMock.calls = [];
    bridgeMock.response = snapshotEnvelope(true);
    const refreshed = await refreshKnowledgeReviews();
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_refresh', args: undefined }
    ]);
    expect(refreshed.refresh_requested).toBe(true);
    expect(refreshed.refresh_succeeded).toBe(true);
  });

  it('rejects malformed snapshot counts, authority, contracts, and unknown freshness', async () => {
    bridgeMock.response = snapshotEnvelope(false, { stale_count: 1 });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = snapshotEnvelope(false, { persistence: true as never });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = snapshotEnvelope(false, {
      contract: 'localcomet.knowledge-review-refresh/1.0'
    });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = snapshotEnvelope(false, {
      current_vault_revision: null,
      freshness_known: false,
      review_states: [
        {
          review_artifact_identity: REVIEW_ID,
          status: 'REVIEW_REQUIRED',
          stale: false
        }
      ]
    });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('creates one exact e9c decision and verifies the complete HARD STOP response', async () => {
    const request = decisionRequest({
      decision: 'REQUEST_CHANGES',
      comment: 'Please clarify the evidence.'
    });
    bridgeMock.response = decisionEnvelope(request);
    const result = await createKnowledgeReviewDecision(request);
    expect(bridgeMock.calls).toEqual([
      {
        command: 'knowledge_review_decision_create',
        args: {
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
        }
      }
    ]);
    expect(result.decision.decision_identity).toMatch(/^kdecision:[0-9a-f]{64}$/);
    expect(result.decision.comment).toBe(request.comment);
    expect(result.hard_stop).toBe(true);
    expect(result.vault_modified).toBe(false);
    expect(result.persistence).toBe(false);
    expect(result.publication).toBe(false);
    expect(Object.isFrozen(result.decision.actor)).toBe(true);
  });

  it('rejects unbound, over-limit, stale, or authority-bearing decisions', async () => {
    await expect(
      createKnowledgeReviewDecision(decisionRequest({
        decision: 'REQUEST_CHANGES',
        comment: '   '
      }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(
      createKnowledgeReviewDecision(decisionRequest({ comment: 'x'.repeat(2_001) }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(
      createKnowledgeReviewDecision(decisionRequest({ actorIdentifier: 'x'.repeat(257) }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(
      createKnowledgeReviewDecision(decisionRequest({
        decision: 'APPROVE',
        changeIdentity: null
      }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(bridgeMock.calls).toHaveLength(0);

    const request = decisionRequest();
    bridgeMock.response = decisionEnvelope(request, { current_vault_revision: SHA_D });
    await expect(createKnowledgeReviewDecision(request)).rejects.toMatchObject({
      code: 'invalid_payload'
    });

    bridgeMock.response = decisionEnvelope(request, {
      vault_modified: true as never
    });
    await expect(createKnowledgeReviewDecision(request)).rejects.toMatchObject({
      code: 'invalid_payload'
    });

    const wrong = decisionEnvelope(request);
    bridgeMock.response = {
      ...wrong,
      decision: {
        ...wrong.decision,
        review_artifact_identity: `kreview:${'9'.repeat(64)}`
      }
    };
    await expect(createKnowledgeReviewDecision(request)).rejects.toMatchObject({
      code: 'invalid_payload'
    });
  });

});
````

### ПУТЬ: desktop/localcomet-desktop/tests/language.test.ts (181 строк, 5996 байт)

````typescript
import { describe, expect, it, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { locale, setLocale, t } from '../src/lib/i18n';
import { getInitialMessages } from '../src/lib/data/mockData';
import type { Language } from '../src/lib/i18n';
import {
  LEGACY_LANGUAGE_KEY,
  UI_PREFERENCES_KEY,
  loadUiPreferences
} from '../src/lib/stores/uiPreferences';

// Minimal localStorage polyfill for node test environment
if (typeof localStorage === 'undefined') {
  const store: Record<string, string> = {};
  globalThis.localStorage = {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { Object.keys(store).forEach(k => delete store[k]); },
    get length() { return Object.keys(store).length; },
    key: (i: number) => Object.keys(store)[i] ?? null
  } as Storage;
}

// Minimal window polyfill for node test environment (needed by persistLanguage guard)
if (typeof window === 'undefined') {
  globalThis.window = { } as any;
}

// Minimal document polyfill for node test environment
if (typeof document === 'undefined') {
  const doc = { documentElement: { lang: '' } } as any;
  globalThis.document = doc;
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.lang = '';
  locale.set('ru');
});

describe('language store', () => {
  it('default language is ru', () => {
    expect(get(locale)).toBe('ru');
  });

  it('invalid stored value falls back to ru', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({ locale: 'fr' }));
    expect(loadUiPreferences().locale).toBe('ru');
  });

  it('selecting English changes visible UI text', () => {
    setLocale('en');
    expect(get(locale)).toBe('en');
    const tf = get(t);
    expect(tf('chat.send')).toBe('Send');
    expect(tf('chat.type_message')).toBe('Type a message…');
    expect(tf('conn.not_connected')).toBe('Not connected');
  });

  it('selecting Russian changes it back', () => {
    setLocale('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
    const tf = get(t);
    expect(tf('chat.send')).toBe('Отправить');
    expect(tf('chat.type_message')).toBe('Введите сообщение…');
    expect(tf('conn.not_connected')).toBe('Не подключено');
  });

  it('selected language persists to the versioned preference record', () => {
    setLocale('en');
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}')).toEqual({
      theme: 'system',
      locale: 'en',
      diagnosticsPanel: 'closed'
    });
    expect(localStorage.getItem(LEGACY_LANGUAGE_KEY)).toBeNull();
    setLocale('ru');
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}').locale).toBe('ru');
  });

  it('runtime/model state is not reset by language switch', () => {
    setLocale('ru');
    setLocale('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
  });

  it('drawer state is not reset by language switch', () => {
    setLocale('en');
    expect(get(locale)).toBe('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
  });

  it('selector opens and closes', () => {
    expect(() => setLocale('en')).not.toThrow();
    expect(() => setLocale('ru')).not.toThrow();
  });

  it('Escape closes selector', () => {
    setLocale('en');
    expect(get(locale)).toBe('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
  });

  it('technical IDs remain untranslated', () => {
    setLocale('en');
    const tf = get(t);
    expect(tf('minimal')).toBe('minimal');
    expect(tf('native-localcomet')).toBe('native-localcomet');
    expect(tf('llama.cpp')).toBe('llama.cpp');
    expect(tf('LocalComet')).toBe('LocalComet');
  });

  it('document.documentElement.lang updates correctly', () => {
    setLocale('en');
    expect(document.documentElement.lang).toBe('en');
    setLocale('ru');
    expect(document.documentElement.lang).toBe('ru');
  });

  it('switching repeatedly works', () => {
    const langs: Language[] = ['ru', 'en', 'ru', 'en', 'en', 'ru'];
    for (const lang of langs) {
      setLocale(lang);
      expect(get(locale)).toBe(lang);
    }
  });

  it('getInitialMessages returns Russian for ru', () => {
    const msgs = getInitialMessages('ru');
    expect(msgs[0].body).toBe('Начать диалог.');
    expect(msgs[1].body).toContain('Модель не подключена');
    expect(msgs[1].demo).toBe(true);
  });

  it('getInitialMessages returns English for en', () => {
    const msgs = getInitialMessages('en');
    expect(msgs[0].body).toBe('Start dialog.');
    expect(msgs[1].body).toContain('Model is not connected');
    expect(msgs[1].demo).toBe(true);
  });

  it('common.skip_link is translated correctly', () => {
    setLocale('ru');
    expect(get(t)('common.skip_link')).toBe('Перейти к чату');
    setLocale('en');
    expect(get(t)('common.skip_link')).toBe('Skip to chat');
  });

  it('English mode has no Russian strings in UI-relevant keys', () => {
    setLocale('en');
    const tf = get(t);
    const keysToCheck = [
      'chat.send', 'chat.type_message', 'conn.not_connected',
      'common.skip_link', 'demo.start_dialog', 'demo.model_not_connected',
      'lang.select', 'theme.manage', 'project.detail'
    ];
    for (const key of keysToCheck) {
      const val = tf(key);
      expect(val).not.toMatch(/[а-яё]/i);
      expect(val).not.toMatch(/[А-ЯЁ]/);
    }
  });

  it('getInitialMessages matches t() demo keys', () => {
    setLocale('en');
    const tfEn = get(t);
    const enMsgs = getInitialMessages('en');
    expect(enMsgs[0].body).toBe(tfEn('demo.start_dialog'));
    expect(enMsgs[1].body).toBe(tfEn('demo.model_not_connected'));
    setLocale('ru');
    const tfRu = get(t);
    const ruMsgs = getInitialMessages('ru');
    expect(ruMsgs[0].body).toBe(tfRu('demo.start_dialog'));
    expect(ruMsgs[1].body).toBe(tfRu('demo.model_not_connected'));
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/managed-artifacts.test.ts (612 строк, 23155 байт)

````typescript
import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ManagedRuntimePanel from '../src/lib/components/model/ManagedRuntimePanel.svelte';
import * as modelGatewayBridge from '../src/lib/bridge/modelGateway';
import {
  cancelArtifactDownload,
  getManagedArtifactValidationStatus,
  getArtifactDownloadState,
  getManagedInstalledArtifacts,
  getManagedModelCatalog,
  getManagedModelReadiness,
  getManagedRuntimeCatalog,
  listApprovedDownloadableArtifacts,
  removeManagedModel,
  startApprovedArtifactDownload
} from '../src/lib/bridge/modelGateway';
import {
  managedRuntimeStore,
  managedConnectionBusy,
  modelGatewayStore,
  connectSelectedManagedModel,
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
const DOWNLOAD_JOB_ID = 'd'.repeat(64);

let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let responses: Record<string, unknown> = {};

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    invokeCalls.push({ command, args });
    const response = responses[command];
    return typeof response === 'function'
      ? await (response as (args?: Record<string, unknown>) => unknown)(args)
      : response ?? {};
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

function downloadableArtifactFixture(kind: 'runtime' | 'model') {
  const artifactId = kind === 'runtime' ? RUNTIME_ID : MODEL_ID;
  return {
    artifact_id: artifactId,
    kind,
    display_name: kind === 'runtime' ? 'llama.cpp b6000' : 'Qwen2.5 1.5B Instruct Q4_K_M',
    source_identity: kind === 'runtime' ? 'ggml-org/llama.cpp' : 'Qwen/Qwen2.5-1.5B-Instruct-GGUF',
    expected_bytes: kind === 'runtime' ? RUNTIME_BYTES : MODEL_BYTES,
    license_id: kind === 'runtime' ? 'MIT' : 'Apache-2.0',
    format: kind === 'runtime' ? 'zip' : 'GGUF',
    quantization: kind === 'runtime' ? null : 'Q4_K_M',
    user_confirmation_required: true,
    automatic_download: false
  };
}

function downloadStateFixture(lifecycle = 'awaiting_confirmation') {
  return {
    job_id: DOWNLOAD_JOB_ID,
    artifact_id: RUNTIME_ID,
    lifecycle,
    expected_bytes: RUNTIME_BYTES,
    received_bytes: 0,
    percent: 0,
    started_utc_ms: 1_750_000_000_000,
    updated_utc_ms: 1_750_000_000_000,
    error_code: null
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
    },
    model_binding_set: {
      provider_id: 'managed-llama-cpp',
      harness_id: 'minimal',
      model_id: MODEL_ID,
      binding_fingerprint: 'f'.repeat(64),
      discovered_fingerprint: '9'.repeat(64),
      persistence: false,
      runtime_instance_id: 'd'.repeat(32)
    },
    list_approved_downloadable_artifacts: [downloadableArtifactFixture('runtime'), downloadableArtifactFixture('model')],
    start_approved_artifact_download: downloadStateFixture(),
    get_artifact_download_state: downloadStateFixture(),
    cancel_artifact_download: downloadStateFixture('cancelling'),
    remove_managed_model: { model_id: MODEL_ID, removed: true }
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

  it('uses only narrow approved-acquisition commands and never accepts a URL or destination', async () => {
    const artifacts = await listApprovedDownloadableArtifacts();
    await startApprovedArtifactDownload(RUNTIME_ID);
    await getArtifactDownloadState(DOWNLOAD_JOB_ID);
    await cancelArtifactDownload(DOWNLOAD_JOB_ID);
    await removeManagedModel(MODEL_ID);

    expect(artifacts.map((artifact) => artifact.artifact_id)).toEqual([RUNTIME_ID, MODEL_ID]);
    expect(invokeCalls).toEqual([
      { command: 'list_approved_downloadable_artifacts', args: undefined },
      { command: 'start_approved_artifact_download', args: { artifactId: RUNTIME_ID, confirmed: true } },
      { command: 'get_artifact_download_state', args: { jobId: DOWNLOAD_JOB_ID } },
      { command: 'cancel_artifact_download', args: { jobId: DOWNLOAD_JOB_ID } },
      { command: 'remove_managed_model', args: { modelId: MODEL_ID, confirmed: true } }
    ]);
    expect(JSON.stringify(invokeCalls)).not.toMatch(/url|destination|header|sha256/i);
  });

  it('rejects path-like artifact IDs and malformed acquisition projections before use', async () => {
    await expect(startApprovedArtifactDownload('../model')).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(getArtifactDownloadState('not-a-job')).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);

    responses.list_approved_downloadable_artifacts = [{ ...downloadableArtifactFixture('runtime'), format: 'GGUF' }];
    await expect(listApprovedDownloadableArtifacts()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('accepts only internally consistent terminal download states', async () => {
    responses.start_approved_artifact_download = {
      ...downloadStateFixture('completed'),
      received_bytes: RUNTIME_BYTES,
      percent: 100
    };
    await expect(startApprovedArtifactDownload(RUNTIME_ID)).resolves.toMatchObject({
      lifecycle: 'completed',
      received_bytes: RUNTIME_BYTES,
      percent: 100
    });

    responses.start_approved_artifact_download = downloadStateFixture('completed');
    await expect(startApprovedArtifactDownload(RUNTIME_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
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

  it('connects the approved managed model once without replacing backend status', async () => {
    await refreshManagedRuntimeStatus();
    const readyStatus = {
      ...runtimeStatusFixture(),
      state: 'Ready',
      model_state: 'Ready',
      inference_ready: true,
      runtime_instance_id: 'd'.repeat(32),
      runtime_instance_fingerprint: 'e'.repeat(64),
      model_id: MODEL_ID,
      model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      binding_fingerprint: '9'.repeat(64)
    };
    responses.managed_runtime_start = () => {
      responses.managed_runtime_status = readyStatus;
      return {
        state: 'Ready',
        model_state: 'Ready',
        inference_ready: true,
        provider_id: 'managed-llama-cpp',
        model_id: MODEL_ID,
        model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
        runtime_instance_id: 'd'.repeat(32),
        runtime_instance_fingerprint: 'e'.repeat(64)
      };
    };

    const first = connectSelectedManagedModel();
    const second = connectSelectedManagedModel();

    expect(first).toBe(second);
    expect(get(managedConnectionBusy)).toBe(true);
    expect(get(managedRuntimeStore).status?.state).toBe('Stopped');
    await expect(first).resolves.toBe(true);
    expect(get(managedConnectionBusy)).toBe(false);
    expect(invokeCalls.filter((call) => call.command === 'managed_runtime_start')).toHaveLength(1);
    expect(invokeCalls.filter((call) => call.command === 'model_binding_set')).toHaveLength(1);
  });

  it('binds an already-ready selected model without restarting its runtime', async () => {
    responses.managed_runtime_status = {
      ...runtimeStatusFixture(),
      state: 'Ready',
      model_state: 'Ready',
      inference_ready: true,
      runtime_instance_id: 'd'.repeat(32),
      runtime_instance_fingerprint: 'e'.repeat(64),
      model_id: MODEL_ID,
      model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      binding_fingerprint: '9'.repeat(64)
    };
    await refreshManagedRuntimeStatus();

    await expect(connectSelectedManagedModel()).resolves.toBe(true);

    expect(invokeCalls.filter((call) => call.command === 'managed_runtime_start')).toHaveLength(0);
    expect(invokeCalls.filter((call) => call.command === 'model_binding_set')).toHaveLength(1);
  });

  it('keeps authoritative stopped status when readiness validation fails', async () => {
    await refreshManagedRuntimeStatus();
    responses.managed_model_readiness = readinessFixture({
      model_status: 'not_installed',
      readiness: 'model_not_installed',
      launchable: false
    });

    await expect(connectSelectedManagedModel()).resolves.toBe(false);

    expect(get(managedRuntimeStore).status?.state).toBe('Stopped');
    expect(get(managedRuntimeStore).lastError?.code).toBe('model_not_ready');
    expect(invokeCalls.filter((call) => call.command === 'managed_runtime_start')).toHaveLength(0);
  });

  it('preserves the sanitized backend runtime error during refresh', async () => {
    responses.managed_runtime_status = {
      ...runtimeStatusFixture(),
      state: 'Failed',
      model_state: 'Failed',
      last_error: 'managed runtime exited before readiness'
    };

    await refreshManagedRuntimeStatus();

    expect(get(managedRuntimeStore).lastError).toEqual({
      code: 'runtime_unavailable',
      message: 'managed runtime exited before readiness'
    });
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
````

### ПУТЬ: desktop/localcomet-desktop/tests/model-gateway.test.ts (216 строк, 10921 байт)

````typescript
import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ModelGatewayPanel from '../src/lib/components/model/ModelGatewayPanel.svelte';
import ManagedRuntimePanel from '../src/lib/components/model/ManagedRuntimePanel.svelte';
import {
  getModelGatewayCatalog,
  listModelGatewayModels,
  probeModelGateway,
  setModelBinding,
  startModelTurn,
  subscribeModelGatewayEvents
} from '../src/lib/bridge/modelGateway';
import {
  applyModelGatewayEvent,
  inferenceRequestStore,
  modelGatewayStore,
  resetModelGatewayStore,
  setGatewayPortText
} from '../src/lib/stores/modelGateway';
import { appendAcceptedChatTurn, resetShellStores } from '../src/lib/stores/shellStore';
import type { ModelGatewayEvent } from '../src/lib/types/modelGateway';

const TURN_ID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const FINGERPRINT = 'b'.repeat(64);
const TRUST_CATALOG = {
  schema_version: 1,
  catalog_id: 'localcomet-approved-artifacts',
  catalog_version: '1.0.0',
  catalog_digest: 'c'.repeat(64)
};
let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let listener: ((event: { payload: unknown }) => void) | null = null;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    invokeCalls.push({ command, args });
    if (command === 'model_gateway_catalog') return catalogFixture();
    if (command === 'managed_runtime_status') return { engine: 'llama.cpp', state: 'NotInstalled', installation: 'Not installed', runtime_version: null, runtime_instance_id: null, runtime_instance_fingerprint: null, model_id: null, model_display_name: null, binding_fingerprint: null, model_state: 'Unavailable', inference_ready: false, last_error: null };
    if (command === 'managed_runtime_catalog') return { ...TRUST_CATALOG, runtimes: [] };
    if (command === 'managed_model_catalog') return { ...TRUST_CATALOG, engine: 'llama.cpp', model_root: '<MANAGED_MODEL_ROOT>', models: [], maximum_models: 32 };
    if (command === 'managed_installed_artifacts') return { ...TRUST_CATALOG, artifacts: [] };
    if (command === 'managed_runtime_logs') return { stdout_tail: [], stderr_tail: [] };
    if (command === 'model_gateway_probe') return { status: 'Ready', provider_id: 'openai-compatible-local', host: '127.0.0.1', port: args?.port, base_path: '/v1', model_count: 1 };
    if (command === 'model_gateway_list_models') return { provider_id: 'openai-compatible-local', host: '127.0.0.1', port: args?.port, models: [{ model_id: 'local-model' }], discovered_fingerprint: FINGERPRINT };
    if (command === 'model_binding_set') return { provider_id: 'openai-compatible-local', harness_id: args?.harnessId, host: '127.0.0.1', port: args?.port, base_path: '/v1', model_id: args?.modelId, binding_fingerprint: FINGERPRINT, discovered_fingerprint: FINGERPRINT, persistence: false };
    if (command === 'model_turn_start') return {
      request_id: args?.requestId,
      chat_session_id: args?.chatSessionId,
      turn_id: args?.requestId,
      state: 'Accepted',
      model_id: args?.modelId,
      submitted_at_unix_ms: args?.submittedAtUnixMs,
      max_tokens: args?.maxTokens,
      binding_fingerprint: args?.bindingFingerprint,
      ...(Array.isArray(args?.fileIds) && args.fileIds.length > 0 ? {
        file_context: {
          source_bytes: 10,
          source_characters: 10,
          included_bytes: 5,
          included_characters: 5,
          truncated: true,
          files: [{ file_id: args.fileIds[0], filename: 'notes.md', original_bytes: 10, original_characters: 10, included_bytes: 5, included_characters: 5, inclusion: 'bounded_excerpt' }]
        }
      } : {})
    };
    return {};
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_event: string, callback: (event: { payload: unknown }) => void): Promise<() => void> => {
    listener = callback;
    return () => undefined;
  })
}));

function installTauriMock(): void {
  invokeCalls = [];
  listener = null;
}

function catalogFixture() {
  return {
    gateway_version: 'v6.84.5',
    providers: [
      { provider_id: 'openai-compatible-local', label: 'OpenAI-compatible local', scheme: 'http', host: '127.0.0.1', base_path: '/v1' },
      { provider_id: 'managed-llama-cpp', label: 'LocalComet managed llama.cpp', scheme: 'internal', host: '127.0.0.1', base_path: '/v1' }
    ],
    harnesses: [{ harness_id: 'minimal', label: 'Minimal' }, { harness_id: 'native-localcomet', label: 'Native LocalComet' }],
    persistence: false,
    tools_available: false
  };
}

function modelEvent(method: ModelGatewayEvent['method'], sequence: number, patch: Partial<ModelGatewayEvent> = {}): ModelGatewayEvent {
  const stateByMethod = {
    'model.turn.started': 'Streaming',
    'model.output.delta': 'Streaming',
    'model.turn.completed': 'Completed',
    'model.turn.cancelled': 'Cancelled',
    'model.turn.timed_out': 'TimedOut',
    'model.turn.failed': 'Failed'
  } as const;
  return {
    method,
    sequence,
    reply_to: TURN_ID,
    request_id: TURN_ID,
    chat_session_id: 'local-chat',
    turn_id: TURN_ID,
    state: patch.state ?? stateByMethod[method],
    text: patch.text ?? null,
    model_called: patch.model_called ?? true,
    tools_executed: 0,
    persistence: false,
    generated_bytes: patch.generated_bytes ?? 0,
    provider_id: 'openai-compatible-local',
    harness_id: 'minimal',
    model_id: 'local-model',
    binding_fingerprint: FINGERPRINT
  };
}

describe('Local Model Gateway frontend', () => {
  beforeEach(() => {
    resetModelGatewayStore();
    resetShellStores();
    installTauriMock();
  });

  it('uses exactly the fixed model gateway commands', async () => {
    await getModelGatewayCatalog();
    await probeModelGateway(1234);
    await listModelGatewayModels(1234);
    await setModelBinding({ providerId: 'openai-compatible-local', harnessId: 'minimal', port: 1234, modelId: 'local-model' });
    await startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', locale: 'ru', bindingFingerprint: FINGERPRINT });
    expect(invokeCalls.map((call) => call.command)).toEqual([
      'model_gateway_catalog',
      'model_gateway_probe',
      'model_gateway_list_models',
      'model_binding_set',
      'model_turn_start'
    ]);
    expect(JSON.stringify(invokeCalls)).not.toContain('http://');
    expect(JSON.stringify(invokeCalls)).not.toContain('api');
    expect(invokeCalls.at(-1)?.args).toMatchObject({ prompt: 'hello', fileIds: [], locale: 'ru' });
  });

  it('passes only validated opaque file identities to the model command', async () => {
    const fileId = 'd'.repeat(64);
    const response = await startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', fileIds: [fileId], locale: 'ru', bindingFingerprint: FINGERPRINT });
    expect(invokeCalls.at(-1)?.args?.fileIds).toEqual([fileId]);
    expect(response.file_context).toMatchObject({ included_bytes: 5, truncated: true });
    await expect(startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', fileIds: ['C:\\temp\\notes.md'], locale: 'ru', bindingFingerprint: FINGERPRINT })).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(1);
  });

  it('rejects invalid ports before invoking Tauri', async () => {
    await expect(probeModelGateway(80)).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);
    setGatewayPortText('12x34');
    expect(get(modelGatewayStore).portText).toBe('1234');
  });

  it('rejects an unsupported assistant locale before invoking Tauri', async () => {
    await expect(startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', locale: 'fr' as 'ru', bindingFingerprint: FINGERPRINT })).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);
  });

  it('subscribes to model events and updates truthful telemetry', async () => {
    const seen: string[] = [];
    await subscribeModelGatewayEvents((event) => seen.push(event.method));
    listener?.({ payload: { method: 'model.output.delta', sequence: 1, reply_to: TURN_ID, request_id: TURN_ID, chat_session_id: 'local-chat', turn_id: TURN_ID, model_id: 'local-model', state: 'Streaming', text: 'hi', metadata: { model_called: true, tools_executed: 0, persistence: false, generated_bytes: 2, provider_id: 'openai-compatible-local', harness_id: 'minimal', model_id: 'local-model', binding_fingerprint: FINGERPRINT } } });
    expect(seen).toEqual(['model.output.delta']);
    modelGatewayStore.update((state) => ({
      ...state,
      binding: {
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        host: '127.0.0.1',
        port: 1234,
        base_path: '/v1',
        model_id: 'local-model',
        binding_fingerprint: FINGERPRINT,
        discovered_fingerprint: FINGERPRINT,
        persistence: false
      }
    }));
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
    appendAcceptedChatTurn(TURN_ID, 'hello');
    applyModelGatewayEvent(modelEvent('model.turn.started', 0));
    applyModelGatewayEvent(modelEvent('model.output.delta', 1, { text: 'hello' }));
    applyModelGatewayEvent(modelEvent('model.turn.completed', 2, { state: 'Completed' }));
    const state = get(modelGatewayStore);
    expect(state.modelCalled).toBe(true);
    expect(state.toolsExecuted).toBe(0);
    expect(state.persistence).toBe('Off');
    expect(state.status).toBe('Completed');
    expect(state.generatedText).toBe('hello');
  });

  it('renders no URL, API key, header, tool or attachment controls', () => {
    const body = render(ModelGatewayPanel).body;
    expect(body).toContain('OpenAI-compatible local');
    expect(body).toContain('127.0.0.1');
    expect(body).not.toMatch(/URL|API key|Headers|Temperature|Attachments|Tool controls/i);
  });

  it('renders managed runtime without URL, port, API-key, executable or path controls', () => {
    const body = render(ManagedRuntimePanel).body;
    expect(body).toContain('Managed llama.cpp');
    expect(body).toContain('Not installed');
    expect(body).not.toMatch(/URL|Port|API key|Executable|Model path|Environment|Arguments/i);
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/review-center-store.test.ts (673 строк, 25090 байт)

````typescript
import { get } from 'svelte/store';
import { describe, expect, it, vi } from 'vitest';
import type { KnowledgeReviewClient } from '../src/lib/bridge/knowledgeReview';
import { REVIEW_FIXTURES } from '../src/lib/data/reviewFixtures';
import { createReviewCenterController } from '../src/lib/stores/reviewCenter';
import type {
  KnowledgeChangeReviewProjection,
  KnowledgeReviewGetEnvelope,
  KnowledgeReviewDecisionCreateEnvelope,
  KnowledgeReviewListEnvelope,
  KnowledgeReviewSnapshotEnvelope,
  KnowledgeReviewSummaryProjection,
  ReviewStatus
} from '../src/lib/types/knowledgeReview';

const REVIEW_A = `kreview:${'a'.repeat(64)}`;
const REVIEW_B = `kreview:${'b'.repeat(64)}`;
const PROPOSAL = `kprop:${'c'.repeat(64)}`;
const CHANGE = `kchange:${'d'.repeat(64)}`;
const HASH = `sha256:${'e'.repeat(64)}`;

type Deferred<T> = Readonly<{
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}>;

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function summary(
  reviewArtifactIdentity = REVIEW_A,
  status: ReviewStatus = 'CLEAR'
): KnowledgeReviewSummaryProjection {
  const blocked = status === 'BLOCKED';
  return {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status,
    blocked,
    proposal_id: PROPOSAL,
    target_stable_id: `review.${reviewArtifactIdentity.slice(-8)}`,
    operation: 'UPDATE_EXISTING',
    expected_vault_revision: HASH,
    observed_vault_revision: HASH,
    review_artifact_identity: reviewArtifactIdentity,
    change_identity: blocked ? null : CHANGE,
    finding_count: blocked ? 1 : 0,
    normal_change_material_present: !blocked,
    detail_projection_truncated: false
  };
}

function listEnvelope(
  items: readonly KnowledgeReviewSummaryProjection[],
  patch: Partial<KnowledgeReviewListEnvelope> = {}
): KnowledgeReviewListEnvelope {
  return {
    contract: 'localcomet.knowledge-review-list/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    offset: 0,
    limit: 50,
    total_count: items.length,
    returned_count: items.length,
    truncated: false,
    next_offset: null,
    items,
    ...patch
  };
}

function reviewIdentity(index: number): string {
  return `kreview:${index.toString(16).padStart(64, '0')}`;
}

function reviewSummaries(count: number): readonly KnowledgeReviewSummaryProjection[] {
  return Object.freeze(
    Array.from({ length: count }, (_, index) => summary(reviewIdentity(index + 1)))
  );
}

function pagedListEnvelope(
  allItems: readonly KnowledgeReviewSummaryProjection[],
  offset: number,
  limit = 50
): KnowledgeReviewListEnvelope {
  const items = allItems.slice(offset, offset + limit);
  const nextOffset = offset + items.length;
  const truncated = nextOffset < allItems.length;
  return listEnvelope(items, {
    offset,
    limit,
    total_count: allItems.length,
    returned_count: items.length,
    truncated,
    next_offset: truncated ? nextOffset : null
  });
}

function snapshotEnvelope(
  states: readonly { review_artifact_identity: string; status: ReviewStatus; stale: boolean | null }[] = [
    { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: false },
    { review_artifact_identity: REVIEW_B, status: 'CLEAR', stale: false }
  ],
  refreshRequested = false
): KnowledgeReviewSnapshotEnvelope {
  return {
    contract: refreshRequested
      ? 'localcomet.knowledge-review-refresh/1.0'
      : 'localcomet.knowledge-review-snapshot/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.6',
    sidecar_runtime_version: 'v6.84.3',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    refresh_requested: refreshRequested,
    refresh_succeeded: refreshRequested,
    current_vault_revision: HASH,
    freshness_known: true,
    knowledge_state: 'READY',
    last_error_code: null,
    inbox_count: states.length,
    stale_count: states.filter((state) => state.stale === true).length,
    blocked_count: states.filter((state) => state.status === 'BLOCKED').length,
    session_decision_count: 0,
    review_states: states,
    hard_stop: true,
    persistence: false,
    vault_write_authority: false,
    publication_authority: false
  };
}

function decisionEnvelope(
  request: Parameters<KnowledgeReviewClient['createDecision']>[0]
): KnowledgeReviewDecisionCreateEnvelope {
  return {
    contract: 'localcomet.knowledge-review-decision-create/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.6',
    sidecar_runtime_version: 'v6.84.3',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    duplicate: false,
    current_vault_revision: request.observedVaultRevision,
    decision: {
      projection_contract: 'localcomet.knowledge-review-ui/1.0',
      kind: 'HUMAN_REVIEW_DECISION',
      contract_version: 'localcomet.knowledge-change-review-decision/1.0',
      review_contract_version: request.reviewContractVersion,
      review_status: 'CLEAR',
      proposal_id: request.proposalId,
      review_artifact_identity: request.reviewArtifactIdentity,
      change_identity: request.changeIdentity,
      observed_vault_revision: request.observedVaultRevision,
      decision: request.decision,
      comment: request.comment,
      actor: {
        actor_identifier: request.actorIdentifier,
        display_name: request.actorDisplayName,
        source: request.actorSource
      },
      decision_identity: `kdecision:${'f'.repeat(64)}`,
      hard_stop: true,
      review_decision_only: true,
      actor_metadata_evidence_only: true,
      human_identity_authenticated: false,
      grants_write_authority: false,
      grants_vault_write_authority: false,
      grants_persistence_authority: false,
      grants_publication_authority: false,
      grants_merge_authority: false,
      grants_rebase_authority: false,
      grants_execution_authority: false,
      grants_policy_authority: false,
      grants_model_gateway_authority: false,
      grants_tauri_frontend_authority: false,
      grants_automatic_approval_authority: false
    },
    hard_stop: true,
    vault_modified: false,
    persistence: false,
    publication: false
  };
}

function getEnvelope(
  reviewArtifactIdentity = REVIEW_A,
  status: ReviewStatus = 'CLEAR'
): KnowledgeReviewGetEnvelope {
  const blocked = status === 'BLOCKED';
  const preview = {
    preview_text: 'bounded text',
    is_preview: true,
    truncated: false,
    original_utf8_bytes: 12,
    original_line_count: 1,
    preview_utf8_bytes: 12,
    preview_line_count: 1
  };
  const projection = {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status,
    proposal_id: PROPOSAL,
    proposal_content_hash: HASH,
    operation: 'UPDATE_EXISTING',
    target_stable_id: `review.${reviewArtifactIdentity.slice(-8)}`,
    expected_vault_revision: HASH,
    observed_vault_revision: HASH,
    validation_outcome: 'VALID',
    validation_snapshot: {
      value: { type_tag: 'mapping', scalar_value: null, mapping_items: [], sequence_items: [] },
      truncated: false
    },
    source_validation_findings: { items: [], original_count: 0, truncated: false },
    stable_id_set_hash: HASH,
    proposed_content_snapshot: {
      title: 'Real review',
      body_text: { ...preview, raw_text_hash: HASH, semantic_text_hash: HASH },
      type: 'architecture',
      status: 'current',
      knowledge_layer: 'current_source_truth',
      evidence_class: 'A',
      authority: 'source',
      canonical: true,
      canonical_scope: null,
      aliases: { items: [], original_count: 0, truncated: false },
      releases: { items: [], original_count: 0, truncated: false },
      source_paths: { items: ['modules/review.py'], original_count: 1, truncated: false },
      evidence_refs: { items: [], original_count: 0, truncated: false },
      supersedes: { items: [], original_count: 0, truncated: false },
      superseded_by: { items: [], original_count: 0, truncated: false },
      updated: '2026-07-16',
      last_reviewed: '2026-07-16',
      verified_at: null
    },
    findings: { items: [], original_count: 0, truncated: false },
    before_source_byte_hash: blocked ? null : HASH,
    before_text_raw_hash: blocked ? null : HASH,
    before_semantic_text_hash: blocked ? null : HASH,
    proposed_text_raw_hash: HASH,
    proposed_semantic_text_hash: HASH,
    diff: blocked
      ? null
      : {
          preview,
          preview_truncated: false,
          preview_is_full_diff: true,
          full_diff_present: true,
          full_diff_hash: HASH,
          full_diff_utf8_bytes: 12
        },
    representation_delta: blocked
      ? null
      : {
          before_present: true,
          after_present: true,
          before_line_endings: {
            crlf_count: 0,
            lf_count: 1,
            cr_count: 0,
            terminal_newline: true
          },
          after_line_endings: {
            crlf_count: 0,
            lf_count: 1,
            cr_count: 0,
            terminal_newline: true
          },
          terminal_newline_changed: false,
          after_source_bytes_known: true,
          source_bytes_changed_text_identical: false,
          raw_text_changed_semantic_equal: false,
          semantic_content_changed: true,
          identity: HASH
        },
    change_identity: blocked ? null : CHANGE,
    review_artifact_identity: reviewArtifactIdentity,
    human_review_preview: preview
  } as KnowledgeChangeReviewProjection;
  return {
    contract: 'localcomet.knowledge-review-get/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    projection
  };
}

function client(
  list: KnowledgeReviewClient['list'],
  getReview: KnowledgeReviewClient['get'] = async (identity) => getEnvelope(identity),
  snapshot: KnowledgeReviewClient['snapshot'] = async () => snapshotEnvelope(),
  refresh: KnowledgeReviewClient['refresh'] = async () => snapshotEnvelope(undefined, true),
  createDecision: KnowledgeReviewClient['createDecision'] = async (request) =>
    decisionEnvelope(request)
): KnowledgeReviewClient {
  return { list, get: getReview, snapshot, refresh, createDecision };
}

describe('real read-only Review Center store', () => {
  it('starts idle with an empty production queue and no fixture fallback', () => {
    const controller = createReviewCenterController(
      client(async () => listEnvelope([]))
    );
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'idle',
      source: 'LOCAL_CONTROL_PLANE',
      retryable: false,
      totalCount: 0
    });
    expect(get(controller.reviewQueue)).toEqual([]);
    expect(get(controller.selectedReview)).toBeNull();
    expect('localStorage' in globalThis).toBe(false);
  });

  it('moves through loading to truthful empty state', async () => {
    const pending = deferred<KnowledgeReviewListEnvelope>();
    const controller = createReviewCenterController(client(() => pending.promise));
    const loading = controller.loadReviewCenter();
    expect(get(controller.reviewCenterState).status).toBe('loading');
    pending.resolve(listEnvelope([]));
    await expect(loading).resolves.toBe(true);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'empty',
      source: 'LOCAL_CONTROL_PLANE',
      returnedCount: 0,
      truncated: false,
      nextOffset: null
    });
    expect(get(controller.reviewQueue)).toEqual([]);
  });

  it('loads exactly 50 items in one bounded page', async () => {
    const items = reviewSummaries(50);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const controller = createReviewCenterController(client(list));
    await expect(controller.loadReviewCenter()).resolves.toBe(true);
    expect(list).toHaveBeenCalledTimes(1);
    expect(list).toHaveBeenCalledWith(0, 50);
    expect(get(controller.reviewQueue)).toHaveLength(50);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'ready',
      totalCount: 50,
      returnedCount: 50,
      truncated: false,
      nextOffset: null
    });
  });

  it('aggregates 51 items across two pages before exposing ready state', async () => {
    const items = reviewSummaries(51);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const getReview = vi.fn(async (identity: string) => getEnvelope(identity));
    const controller = createReviewCenterController(client(list, getReview));
    await expect(controller.loadReviewCenter()).resolves.toBe(true);
    expect(list.mock.calls).toEqual([[0, 50], [50, 50]]);
    expect(get(controller.reviewQueue)).toHaveLength(51);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'ready',
      totalCount: 51,
      returnedCount: 51,
      truncated: false,
      nextOffset: null
    });
    expect(getReview).toHaveBeenCalledWith(reviewIdentity(1));
  });

  it('aggregates the full hard maximum of 128 items without persistence', async () => {
    const items = reviewSummaries(128);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const controller = createReviewCenterController(client(list));
    await expect(controller.loadReviewCenter()).resolves.toBe(true);
    expect(list.mock.calls).toEqual([[0, 50], [50, 50], [100, 50]]);
    expect(get(controller.reviewQueue)).toHaveLength(128);
    expect(get(controller.reviewCenterState)).toMatchObject({
      totalCount: 128,
      returnedCount: 128,
      truncated: false,
      nextOffset: null
    });
  });

  it('rejects malformed and repeated pagination continuations', async () => {
    const items = reviewSummaries(52);
    const malformed = createReviewCenterController(
      client(async () => ({
        ...pagedListEnvelope(items, 0),
        next_offset: 49
      }))
    );
    await expect(malformed.loadReviewCenter()).resolves.toBe(false);
    expect(get(malformed.reviewCenterState)).toMatchObject({
      status: 'error',
      error: { code: 'invalid_payload' }
    });

    const repeatedList = vi.fn(async (offset: number) => {
      if (offset === 0) return pagedListEnvelope(items, 0);
      return {
        ...pagedListEnvelope(items, 50),
        truncated: true,
        next_offset: 50
      };
    });
    const repeated = createReviewCenterController(client(repeatedList));
    await expect(repeated.loadReviewCenter()).resolves.toBe(false);
    expect(get(repeated.reviewCenterState)).toMatchObject({
      status: 'error',
      error: { code: 'invalid_payload' }
    });
  });

  it('rejects duplicate identities across pages', async () => {
    const items = [...reviewSummaries(51)];
    items[50] = items[0];
    const controller = createReviewCenterController(
      client(async (offset: number, limit: number) =>
        pagedListEnvelope(items, offset, limit)
      )
    );
    await expect(controller.loadReviewCenter()).resolves.toBe(false);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'error',
      error: { code: 'invalid_payload' },
      returnedCount: 50,
      truncated: true,
      nextOffset: 50
    });
    expect(get(controller.reviewQueue)).toHaveLength(50);
  });

  it('keeps honest partial results when a later page fails and retry reloads all pages', async () => {
    const items = reviewSummaries(51);
    let failedOnce = false;
    const list = vi.fn(async (offset: number, limit: number) => {
      if (offset === 50 && !failedOnce) {
        failedOnce = true;
        throw { code: 'timeout', message: 'second page unavailable' };
      }
      return pagedListEnvelope(items, offset, limit);
    });
    const controller = createReviewCenterController(client(list));
    await expect(controller.loadReviewCenter()).resolves.toBe(false);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'error',
      retryable: true,
      totalCount: 51,
      returnedCount: 50,
      truncated: true,
      nextOffset: 50
    });
    expect(get(controller.reviewQueue)).toHaveLength(50);

    await expect(controller.retryReviewCenter()).resolves.toBe(true);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'ready',
      totalCount: 51,
      returnedCount: 51,
      truncated: false,
      nextOffset: null
    });
    expect(get(controller.reviewQueue)).toHaveLength(51);
  });

  it('preserves a selected identity across a refresh that aggregates later pages', async () => {
    const items = reviewSummaries(51);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const controller = createReviewCenterController(client(list));
    await controller.loadReviewCenter();
    const lastIdentity = reviewIdentity(51);
    expect(controller.selectReview(lastIdentity)).toBe(true);
    await vi.waitFor(() => {
      expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(lastIdentity);
    });
    await expect(controller.refreshReviewCenter()).resolves.toBe(true);
    expect(get(controller.selectedReviewId)).toBe(lastIdentity);
    expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(lastIdentity);
  });

  it('search and filters include artifacts beyond index 49', async () => {
    const items = reviewSummaries(51);
    const controller = createReviewCenterController(
      client(async (offset: number, limit: number) =>
        pagedListEnvelope(items, offset, limit)
      )
    );
    await controller.loadReviewCenter();
    const lastIdentity = reviewIdentity(51);
    controller.setReviewQuery(lastIdentity);
    expect(get(controller.filteredReviewQueue).map((item) => item.reviewArtifactIdentity)).toEqual([
      lastIdentity
    ]);
  });

  it('suppresses an out-of-order get response after a newer selection', async () => {
    const first = deferred<KnowledgeReviewGetEnvelope>();
    const second = deferred<KnowledgeReviewGetEnvelope>();
    const getReview = vi.fn((identity: string) =>
      identity === REVIEW_A ? first.promise : second.promise
    );
    const controller = createReviewCenterController(
      client(async () => listEnvelope([summary(REVIEW_A), summary(REVIEW_B)]), getReview)
    );
    const initialLoad = controller.loadReviewCenter();
    await vi.waitFor(() => {
      expect(get(controller.selectedReviewId)).toBe(REVIEW_A);
    });
    expect(controller.selectReview(REVIEW_B)).toBe(true);
    second.resolve(getEnvelope(REVIEW_B));
    await Promise.resolve();
    await Promise.resolve();
    expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(REVIEW_B);
    first.resolve(getEnvelope(REVIEW_A));
    await initialLoad;
    expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(REVIEW_B);
  });

  it('suppresses an older list response after a newer refresh', async () => {
    const oldList = deferred<KnowledgeReviewListEnvelope>();
    const newList = deferred<KnowledgeReviewListEnvelope>();
    let call = 0;
    const controller = createReviewCenterController(
      client(() => (call++ === 0 ? oldList.promise : newList.promise))
    );
    const oldLoad = controller.loadReviewCenter();
    const newLoad = controller.loadReviewCenter();
    newList.resolve(listEnvelope([]));
    await newLoad;
    oldList.resolve(listEnvelope([summary()]));
    await oldLoad;
    expect(get(controller.reviewCenterState).status).toBe('empty');
    expect(get(controller.reviewQueue)).toEqual([]);
  });

  it('retries transient failures but not invalid payloads', async () => {
    let calls = 0;
    const transient = createReviewCenterController(
      client(async () => {
        calls += 1;
        if (calls === 1) throw { code: 'timeout', message: 'temporarily unavailable' };
        return listEnvelope([]);
      })
    );
    await expect(transient.loadReviewCenter()).resolves.toBe(false);
    expect(get(transient.reviewCenterState)).toMatchObject({ status: 'error', retryable: true });
    await expect(transient.retryReviewCenter()).resolves.toBe(true);
    expect(get(transient.reviewCenterState).status).toBe('empty');

    const invalid = createReviewCenterController(
      client(async () => { throw { code: 'invalid_payload', message: 'bad contract' }; })
    );
    await invalid.loadReviewCenter();
    expect(get(invalid.reviewCenterState)).toMatchObject({ status: 'error', retryable: false });
    await expect(invalid.retryReviewCenter()).resolves.toBe(false);
  });

  it('keeps empty keyboard selection safe', () => {
    const controller = createReviewCenterController(client(async () => listEnvelope([])));
    expect(controller.moveReviewSelection(1)).toBeNull();
    expect(controller.selectReviewBoundary('first')).toBeNull();
    expect(controller.selectReview('missing')).toBe(false);
  });

  it('retains fixture-only decision behavior only for explicit fixture props', () => {
    const controller = createReviewCenterController(client(async () => listEnvelope([])));
    const fixture = REVIEW_FIXTURES[0];
    expect(fixture.fixture).toBe(true);
    expect(controller.openDecisionDialog(fixture, 'REQUEST_CHANGES')).toBe(true);
    controller.setDecisionComment('Explicit fixture review only.');
    expect(controller.confirmFixtureDecision(fixture)).toBe(true);
    expect(get(controller.fixtureDecisionResult)).toMatchObject({ fixture: true, hardStop: true });
  });

  it('creates a real e9c decision and preserves HARD STOP', async () => {
    const createDecision = vi.fn(async (request) => decisionEnvelope(request));
    const controller = createReviewCenterController(
      client(
        async () => listEnvelope([summary()]),
        async () => getEnvelope(REVIEW_A),
        async () => snapshotEnvelope([
          { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: false }
        ]),
        async () => snapshotEnvelope([
          { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: false }
        ], true),
        createDecision
      )
    );
    await controller.loadReviewCenter();
    const real = get(controller.selectedReview)!;
    expect(controller.openDecisionDialog(real, 'APPROVE')).toBe(true);
    expect(await controller.confirmDecision(real)).toBe(true);
    expect(createDecision).toHaveBeenCalledOnce();
    expect(get(controller.realDecisionResult)).toMatchObject({
      fixture: false,
      hardStop: true,
      vaultModified: false,
      persistence: false,
      publication: false
    });
    expect(get(controller.reviewActivity).some((event) => event.kind === 'DECISION_CREATED')).toBe(true);
  });

  it('blocks every real decision when the exact review is stale', async () => {
    const controller = createReviewCenterController(
      client(
        async () => listEnvelope([summary()]),
        async () => getEnvelope(REVIEW_A),
        async () => snapshotEnvelope([
          { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: true }
        ])
      )
    );
    await controller.loadReviewCenter();
    const real = get(controller.selectedReview)!;
    for (const intent of ['APPROVE', 'REJECT', 'REQUEST_CHANGES'] as const) {
      expect(controller.openDecisionDialog(real, intent)).toBe(false);
      expect(get(controller.decisionDialog).open).toBe(false);
    }
  });

  it('filters and deterministically sorts the bounded queue', async () => {
    const controller = createReviewCenterController(
      client(async () => listEnvelope([
        summary(REVIEW_A, 'BLOCKED'),
        summary(REVIEW_B, 'CLEAR')
      ]))
    );
    await controller.loadReviewCenter();
    expect(get(controller.filteredReviewQueue).map((item) => item.status)).toEqual([
      'BLOCKED',
      'CLEAR'
    ]);
    controller.toggleReviewStatus('CLEAR');
    expect(get(controller.filteredReviewQueue).map((item) => item.reviewArtifactIdentity)).toEqual([
      REVIEW_B
    ]);
    controller.setReviewQuery('no-match');
    expect(get(controller.filteredReviewQueue)).toEqual([]);
    controller.clearReviewFilters();
    expect(get(controller.filteredReviewQueue)).toHaveLength(2);
  });

  it('reset invalidates pending work without persistence or duplicate state', async () => {
    const pending = deferred<KnowledgeReviewListEnvelope>();
    const controller = createReviewCenterController(client(() => pending.promise));
    const load = controller.loadReviewCenter();
    controller.resetReviewCenterStore();
    pending.resolve(listEnvelope([summary()]));
    await load;
    expect(get(controller.reviewCenterState).status).toBe('idle');
    expect(get(controller.reviewQueue)).toEqual([]);
  });
});
````

