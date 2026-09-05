import { derived, get, writable } from 'svelte/store';
import { DEFAULT_CONVERSATION_ID } from './conversationStore';
import { parseToolCallResult } from '$lib/tools/computerUseEnvelope';
import {
  extractBrokerContinuationAndScrub,
  redactGrantRefsInPlace,
  stringifyForPersistence,
  type BrokerContinuationHandle
} from '$lib/security/redactContinuation';
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
  MODEL_REQUEST_SEED,
  normalizeGatewayError,
  probeModelGateway,
  setModelBinding,
  startManagedRuntime,
  startManagedRuntimeTrusted,
  startModelTurn,
  stopManagedRuntime,
  stopManagedRuntimeTrusted,
  subscribeModelGatewayEvents
} from '$lib/bridge/modelGateway';
import type {
  ApprovedModelSummary,
  ApprovedRuntimeSummary,
  GatewayCatalog,
  GatewayStatus,
  HarnessId,
  InferenceRequestState,
  ManagedArtifactValidationSummary,
  ManagedCatalogIdentity,
  ManagedInstalledArtifacts,
  ManagedModelCatalog,
  ManagedModelSummary,
  ModelReadinessSummary,
  ManagedRuntimeCatalog,
  ManagedRuntimeLogs,
  ManagedRuntimeState,
  ManagedRuntimeStatus,
  ModelBinding,
  ModelGatewayEvent,
  ModelSummary,
  ModelToolCall,
  SanitizedGatewayError
} from '$lib/types/modelGateway';
import {
  activeWorkspace,
  computeMode,
  agentPermissions,
  appendAcceptedChatTurn,
  appendAssistantChunk,
  appendAssistantReasoningChunk,
  effortLevel,
  setAssistantToolCalls,
  updateAssistantToolResult,
  chatMessages,
  finalizeAssistantMessage,
  setComposerDraft,
  setModelConnected
} from '$lib/stores/shellStore';
import { assistantLocaleFor, locale } from '$lib/i18n';
import { reportFilesContextInclusion, reportFilesRequestError } from '$lib/stores/files';
import { workspaceStore } from '$lib/stores/workspace';
import { runToolCall } from '$lib/bridge/approval';
import {
  deriveBoundedBrowserSearchContinuation,
  deriveBoundedNotepadTypeContinuation
} from '$lib/tools/computerUseContinuation';
import { invoke } from '@tauri-apps/api/core';
import { rejectActiveApproval, requestApprovalForTool, setApprovalCorrelation } from '$lib/stores/approvalStore';
import { DEFAULT_BASE_MODEL_ID } from '$lib/stores/modelDefault';
import { computeModeProfile } from '$lib/types/computeMode';

export const MAX_GENERATED_TEXT = 262_144;
// Per-turn generation budget sent to the backend. The previous 256 truncated
// every answer (the "limited/dumb replies" complaint); 4096 matches the
// runtime's raised --n-predict so the server stops being the first clipper.
export const MODEL_REQUEST_MAX_TOKENS = 4_096;
export const INFERENCE_TIMEOUTS_MS = Object.freeze({
  acceptance: 6_000,
  firstToken: 30_000,
  inactivity: 10_000,
  cancelAcknowledgement: 5_000
});
export const MANAGED_INFERENCE_TIMEOUTS_MS = Object.freeze({
  firstToken: 180_000,
  inactivity: 45_000
});
export const MANAGED_HEALTH_POLL_MS = 2_000;
// Live status polling cadence while a managed runtime start is in flight, so
// the UI shows real backend phases instead of a static spinner.
export const MANAGED_START_PROGRESS_POLL_MS = 750;
// Watchdog margin above the Rust-side MODEL_LOAD_TIMEOUT. The supervisor now
// scales the load deadline dynamically up to 600s for large models, so the UI
// watchdog caps the await slightly above that ceiling. If the watchdog fires,
// the UI recovers truthfully while the trailing status refresh converges the
// store once the backend start settles.
export const MANAGED_START_WATCHDOG_MS = 615_000;
const MAX_BUFFERED_EARLY_EVENTS = 2_048;

export interface ModelGatewayState {
  readonly catalog: GatewayCatalog | null;
  readonly portText: string;
  readonly harnessId: HarnessId;
  readonly models: readonly ModelSummary[];
  readonly selectedModelId: string;
  readonly binding: ModelBinding | null;
  readonly activeTurnId: string | null;
  readonly requestId: string | null;
  readonly generatedText: string;
  readonly status: GatewayStatus;
  readonly modelCalled: boolean;
  readonly toolsExecuted: 0;
  readonly persistence: 'Off';
  readonly lastError: SanitizedGatewayError | null;
  readonly initialized: boolean;
}

type ManagedRuntimePanelReadiness = Omit<ModelReadinessSummary, 'model_trust_kind'> & {
  readonly model_trust_kind?: ModelReadinessSummary['model_trust_kind'];
};

export interface ManagedRuntimePanelState {
  readonly status: ManagedRuntimeStatus | null;
  readonly catalogIdentity: ManagedCatalogIdentity | null;
  readonly runtimeCatalog: readonly ApprovedRuntimeSummary[];
  readonly preferredRuntimeId?: string | null;
  readonly catalog: readonly (ManagedModelSummary | ApprovedModelSummary)[];
  readonly installedArtifacts: readonly ManagedArtifactValidationSummary[];
  readonly readiness: ManagedRuntimePanelReadiness | null;
  readonly selectedModelId: string;
  readonly harnessId: HarnessId;
  readonly binding: ModelBinding | null;
  readonly logs: ManagedRuntimeLogs;
  readonly lastError: SanitizedGatewayError | null;
  /** Non-null when auto-selection fell back to a model other than the pinned baseline. */
  readonly fallbackSelectionNotice: string | null;
}

const initialState: ModelGatewayState = {
  catalog: null,
  portText: '1234',
  harnessId: 'minimal',
  models: [],
  selectedModelId: '',
  binding: null,
  activeTurnId: null,
  requestId: null,
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
  preferredRuntimeId: null,
  catalog: [],
  installedArtifacts: [],
  readiness: null,
  selectedModelId: '',
  harnessId: 'minimal',
  binding: null,
  logs: { stdout_tail: [], stderr_tail: [] },
  lastError: null,
  fallbackSelectionNotice: null
};

const initialInferenceState: InferenceRequestState = {
  lifecycle: 'idle',
  requestId: null,
  chatSessionId: null,
  modelId: null,
  effort: null,
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
let unsubscribeManagedModelReady: (() => void) | null = null;
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

// Bounded launch continuation (plan P0.2): a launch_pending computer_use
// spawn is re-observed through cu_broker_observe until the broker reports a
// terminal envelope or its own TTL expires - never respawned, never granted
// a new token. The registry lets Stop/cancel/new-turn revoke the loop so a
// finished turn can never mutate cards afterwards.
const CONTINUATION_FIRST_CHECK_MS = 4000;
const CONTINUATION_POLL_INTERVAL_MS = 2000;
// Safety cap only; the broker's 600s continuation TTL is the real bound and
// answers with a terminal failed envelope when it expires.
const CONTINUATION_MAX_ATTEMPTS = 320;
const activeContinuationRequests = new Set<string>();
// Opaque broker continuation refs keyed by requestId (master prompt Part I).
// In-memory only: raw refs never reach logs, ledger or evidence.
const activeContinuationGrants = new Map<string, { grantRef: string; consumeArgs?: Record<string, unknown> | null }>();
const activeTurnPrompts = new Map<string, string>();
const activeTurnCalls = new Map<string, ModelToolCall>();

type ContinuationTraceEvent = {
  event: string;
  request_id?: string;
  status?: string;
  revoked?: number;
  found?: boolean;
  error_code?: string;
};

/**
 * Bounded, secret-free diagnostic trace for native acceptance only. The raw
 * grant_ref and lease_id never enter this structure; it records only lifecycle
 * transitions and request correlation so Stop/revoke/no-replay can be proven.
 */
function continuationErrorCode(error: unknown): string {
  const raw = typeof error === 'string'
    ? error
    : error && typeof error === 'object'
      ? String((error as { code?: unknown; message?: unknown }).code ?? (error as { message?: unknown }).message ?? '')
      : '';
  const match = raw.match(/[a-z][a-z0-9_]{2,}/g)?.find((token) => token.includes('_'));
  return match ?? 'invoke_failed';
}

function recordContinuationTrace(event: ContinuationTraceEvent): void {
  const target = globalThis as typeof globalThis & {
    __LOCALCOMET_CONTINUATION_TRACE?: ContinuationTraceEvent[];
  };
  const trace = target.__LOCALCOMET_CONTINUATION_TRACE ?? [];
  trace.push({ ...event });
  if (trace.length > 64) trace.splice(0, trace.length - 64);
  target.__LOCALCOMET_CONTINUATION_TRACE = trace;
}

export function cancelComputerUseContinuations(requestId?: string): void {
  const revokeAndProbe = (id: string, grant: { grantRef: string; consumeArgs?: Record<string, unknown> | null }): void => {
    recordContinuationTrace({ event: 'continuation_revoke_requested', request_id: id });
    void invoke('cu_broker_continuation_revoke', {
      grantRef: grant.grantRef,
      reason: 'turn cancelled or stopped'
    }).then((raw) => {
      const response = raw as { revoked?: unknown };
      recordContinuationTrace({
        event: 'continuation_revoke_succeeded',
        request_id: id,
        revoked: typeof response.revoked === 'number' ? response.revoked : 0
      });
      // B3 replay probe: after an authoritative revoke, replay the identical
      // consume through the real broker to prove the revoked grant can never
      // be re-leased. Raw grant material is destroyed right after the probe
      // settles (both success and rejection paths).
      if (grant.consumeArgs && typeof grant.consumeArgs === 'object') {
        void invoke('cu_broker_continuation_consume', grant.consumeArgs)
          .then((raw) => {
            if (raw && (raw as { status?: string }).status === 'leased') {
              recordContinuationTrace({
                event: 'continuation_replay_unexpected_success',
                request_id: id,
                status: 'unexpected_success'
              });
            }
          })
          .catch((error) => {
            const code = continuationErrorCode(error);
            recordContinuationTrace({
              event: 'continuation_replay_rejected',
              request_id: id,
              status: code === 'continuation_replayed' ? 'continuation_replayed' : 'replay_rejected'
            });
          })
          .finally(() => {
            grant.consumeArgs = null;
            grant.grantRef = '';
          });
      }
    }).catch((error) => {
      recordContinuationTrace({ event: 'continuation_revoke_failed', request_id: id, error_code: continuationErrorCode(error) });
    });
    activeContinuationGrants.delete(id);
  };

  if (requestId === undefined) {
    for (const [id, grant] of activeContinuationGrants) {
      revokeAndProbe(id, grant);
    }
    activeContinuationRequests.clear();
    activeTurnPrompts.clear();
    activeTurnCalls.clear();
    return;
  }
  const grant = activeContinuationGrants.get(requestId);
  if (grant) {
    revokeAndProbe(requestId, grant);
  }
  activeContinuationRequests.delete(requestId);
}

export const modelGatewayStore = writable<ModelGatewayState>(initialState);
export const managedRuntimeStore = writable<ManagedRuntimePanelState>(initialManagedState);
export const inferenceRequestStore = writable<InferenceRequestState>(initialInferenceState);
export const inferenceBusy = derived(inferenceRequestStore, (state) =>
  ['submitted', 'accepted', 'streaming', 'awaiting_approval', 'awaiting_verification', 'cancelling'].includes(state.lifecycle)
);
export const managedConnectionBusy = writable(false);
export const managedModelReady = derived(
  [managedRuntimeStore, modelGatewayStore],
  ([managed, gateway]) => isManagedModelReadySnapshot(managed, gateway)
);
export const approvedManagedModelInstalled = derived(managedRuntimeStore, (managed) =>
  managed.catalog.some((model) =>
    modelTrustKind(model) === 'approved_catalog' &&
    managed.installedArtifacts.some((artifact) => artifact.kind === 'model' && artifact.artifact_id === model.model_id && artifact.installation_status === 'valid') &&
    model.compatible_runtime_ids.some((runtimeId) =>
      managed.installedArtifacts.some((artifact) => artifact.kind === 'runtime' && artifact.artifact_id === runtimeId && artifact.installation_status === 'valid')
    )
  )
);
export const gatewayStatus = derived(modelGatewayStore, (state) => state.status);

export async function initializeModelGateway(): Promise<void> {
  if (!unsubscribeManagedModelReady) {
    unsubscribeManagedModelReady = managedModelReady.subscribe((ready) => setModelConnected(ready));
  }
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
      // Model binding is guarded and user-initiated. Boot only refreshes
      // runtime state; the Model Setup drawer performs explicit connection.
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
  unsubscribeManagedModelReady?.();
  unsubscribeManagedModelReady = null;
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
  const pendingSubscription = subscribeModelGatewayEvents(applyModelGatewayEvent, handleModelProtocolError, { toolsEnabled: true }).then((cleanup) => {
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
    if (get(inferenceBusy)) return;
    if (get(managedRuntimeStore).binding) {
      void verifyLiveManagedSession();
    }
    // Never auto-call connectSelectedManagedModel here: it requests the
    // guarded model.binding.set approval and would reopen the modal forever
    // after a user rejection or a closed app. Reconnection is explicit from
    // the Model Setup UI.
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
          message: status.state === 'Failed' ? 'Managed runtime is unavailable' : 'Managed model is not ready'
        }
      }));
      if (!runtimeReady) {
        clearManagedGatewayBinding();
        return false;
      }

      // Binding approval is user-initiated. Health polling only verifies that
      // the already-approved immutable runtime instance is still alive.
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
  const generation = subscriptionGeneration;
  const state = get(modelGatewayStore);
  const port = currentPort();
  const stillCurrent = () => {
    const current = get(modelGatewayStore);
    return generation === subscriptionGeneration &&
      current.harnessId === state.harnessId &&
      current.selectedModelId === state.selectedModelId &&
      Number(current.portText) === port;
  };
  try {
    const binding = await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: state.harnessId,
      port,
      modelId: state.selectedModelId,
      isCurrent: stillCurrent
    });
    if (!stillCurrent()) return;
    modelGatewayStore.update((current) => ({ ...current, binding, status: 'Bound', lastError: null }));
  } catch (error) {
    if (!stillCurrent()) return;
    modelGatewayStore.update((current) => ({ ...current, status: 'Binding required', binding: null, lastError: normalizeGatewayError(error) }));
  }
}

export async function setManagedSelectedModel(modelId: string): Promise<void> {
  const previousModelId = get(managedRuntimeStore).selectedModelId;
  managedRuntimeStore.update((state) => ({
    ...state,
    selectedModelId: modelId,
    // Do not retain an optimistic start for the former selection. Stable
    // backend statuses remain visible until the next authoritative refresh.
    status: state.status?.state === 'Starting' && state.status.model_id !== modelId
      ? null
      : state.status,
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
    if (!readiness.launchable && get(managedRuntimeStore).selectedModelId === modelId) clearManagedGatewayBinding();
  } catch (error) {
    managedRuntimeStore.update((state) => state.selectedModelId === modelId
      ? { ...state, readiness: null, binding: null, lastError: normalizeGatewayError(error) }
      : state);
    if (get(managedRuntimeStore).selectedModelId === modelId) clearManagedGatewayBinding();
  }
}

export function setManagedPreferredRuntime(runtimeId: string): void {
  const state = get(managedRuntimeStore);
  const runtime = state.runtimeCatalog.find((candidate) => candidate.runtime_id === runtimeId);
  if (!runtime) return;
  managedRuntimeStore.update((current) => ({
    ...current,
    preferredRuntimeId: runtimeId,
    binding: null,
    lastError: null
  }));
  clearManagedGatewayBinding();
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
    const previous = get(managedRuntimeStore);
    const [status, runtimeCatalog, modelCatalog, installedArtifacts, logs] = await Promise.all([
      getManagedRuntimeStatus().catch((error) => {
        const normalized = normalizeGatewayError(error);
        if (!previous.selectedModelId && /No managed model is selected/i.test(normalized.message)) {
          return null;
        }
        throw error;
      }),
      getManagedRuntimeCatalog(),
      getManagedModelCatalog(),
      getManagedInstalledArtifacts(),
      getManagedRuntimeLogs()
    ]);
    assertManagedTrustBundle(runtimeCatalog, modelCatalog, installedArtifacts);
    const models: readonly ManagedModelSummary[] = [
      ...modelCatalog.models.map((model) => ({ ...model, trust_kind: 'approved_catalog' as const })),
      ...modelCatalog.custom_models
    ];
    const validations: readonly ManagedArtifactValidationSummary[] = [
      ...installedArtifacts.artifacts,
      ...installedArtifacts.custom_artifacts
    ];
    const preservedSelectedModelId = models.some((model) => model.model_id === previous.selectedModelId)
      ? previous.selectedModelId
      : '';
    const reportedModelId = status?.model_id && models.some((model) => model.model_id === status.model_id)
      ? status.model_id
      : '';
    const autoSelectedModelId = preservedSelectedModelId || reportedModelId
      ? ''
      : selectStrongestInstalledManagedModelId(models, runtimeCatalog.runtimes, validations);
    const selectedModelId = preservedSelectedModelId || reportedModelId || autoSelectedModelId;
    // Truthful fallback signal: silently swapping the pinned baseline model
    // for another installed model must be visible to the user.
    const fallbackSelectionNotice = autoSelectedModelId && autoSelectedModelId !== DEFAULT_BASE_MODEL_ID
      ? autoSelectedModelId
      : null;
    const selectedModel = models.find((model) => model.model_id === selectedModelId);
    const bindingTrusted =
      status?.state === 'Ready' &&
      status?.model_state === 'Ready' &&
      status?.inference_ready &&
      previous.binding !== null &&
      previous.binding.provider_id === 'managed-llama-cpp' &&
      previous.binding.harness_id === previous.harnessId &&
      previous.binding.model_id === selectedModelId &&
      previous.binding.runtime_instance_id === status?.runtime_instance_id &&
      selectedModel !== undefined &&
      isInstalledLaunchable(selectedModel, runtimeCatalog.runtimes, validations);
    managedRuntimeStore.update((state) => ({
      ...state,
      status,
      fallbackSelectionNotice,
      catalogIdentity: catalogIdentityOf(runtimeCatalog),
      runtimeCatalog: runtimeCatalog.runtimes,
      catalog: models,
      installedArtifacts: validations,
      readiness: null,
      selectedModelId,
      logs,
      lastError: null,
      binding: bindingTrusted ? state.binding : null
    }));
    if (!bindingTrusted) clearManagedGatewayBinding();
    if (selectedModelId) await setManagedSelectedModel(selectedModelId);
    const runtimeError = status?.last_error;
    if (runtimeError && !/No managed model is selected/i.test(runtimeError)) {
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
  const generation = subscriptionGeneration;
  let state = get(managedRuntimeStore);
  const stillCurrent = () => generation === subscriptionGeneration &&
    get(managedRuntimeStore).selectedModelId === state.selectedModelId;
  if (!state.selectedModelId) return;
  try {
    const readiness = precomputedReadiness ?? await readManagedModelReadiness(state.selectedModelId);
    if (!stillCurrent()) return;
    const selectedModel = state.catalog.find((model) => model.model_id === state.selectedModelId);
    if (!readiness.launchable || !selectedModel) {
      const error = {
        code: 'model_not_ready',
        message: 'The selected model is not ready to launch'
      };
      managedRuntimeStore.update((current) => ({
        ...current,
        readiness,
        binding: null,
        lastError: error
      }));
      clearManagedGatewayBinding();
      return;
    }
    // One-click model switch: a different active model is unloaded before the
    // selected one starts. Without this the supervisor answers the start with
    // "busy" and the only way out for the user was an app restart. The stop
    // path refreshes authoritative status and settles its own error; only a
    // runtime still stuck in-flight (Stopping) after that aborts the switch,
    // every other outcome proceeds to the start, which fails honestly on its
    // own if the runtime is genuinely busy.
    const activeState = state.status?.state;
    if (
      (activeState === 'Ready' || activeState === 'Starting' || activeState === 'Validating') &&
      state.status?.model_id !== state.selectedModelId
    ) {
      await stopSelectedManagedRuntimeInternal(false);
      state = get(managedRuntimeStore);
      if (state.status?.state === 'Stopping') {
        const error = {
          code: 'runtime_stop_failed',
          message: 'The previously loaded model could not be unloaded before switching'
        };
        managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: error }));
        clearManagedGatewayBinding();
        return;
      }
    }
    const automaticRuntimeId = selectedModel
      ? selectPreferredInstalledManagedRuntimeId(
        selectedModel,
        state.runtimeCatalog,
        state.installedArtifacts,
        readiness.selected_runtime_id
      )
      : readiness.selected_runtime_id;
    const computeProfile = computeModeProfile(get(computeMode));
    const modeRuntimeId = selectedModel
      ? state.runtimeCatalog.find((runtime) =>
        runtime.variant === computeProfile.runtimeVariant &&
        selectedModel.compatible_runtime_ids.includes(runtime.runtime_id)
      )?.runtime_id ?? null
      : null;
    const preferredRuntime = state.runtimeCatalog.find((runtime) => runtime.runtime_id === state.preferredRuntimeId);
    // Compute mode is authoritative for the engine variant. A manually selected
    // runtime is retained only when it matches the requested CPU/Vulkan variant;
    // this prevents CPU mode from accidentally launching the Vulkan artifact.
    const requestedRuntimeId = (preferredRuntime?.variant === computeProfile.runtimeVariant
      ? preferredRuntime.runtime_id
      : null) ?? modeRuntimeId ?? state.preferredRuntimeId ?? automaticRuntimeId;
    if (!requestedRuntimeId) {
      const error = { code: 'runtime_not_selected', message: 'No compute engine is selected' };
      managedRuntimeStore.update((current) => ({ ...current, readiness, binding: null, lastError: error }));
      clearManagedGatewayBinding();
      return;
    }
    const requestedRuntime = state.runtimeCatalog.find((runtime) => runtime.runtime_id === requestedRuntimeId);
    const requestedRuntimeInstalled = state.installedArtifacts.some((artifact) =>
      artifact.kind === 'runtime' && artifact.artifact_id === requestedRuntimeId && artifact.installation_status === 'valid'
    );
    const requestedRuntimeCompatible = selectedModel?.compatible_runtime_ids.includes(requestedRuntimeId) === true;
    if (!requestedRuntime || !requestedRuntimeInstalled || !requestedRuntimeCompatible) {
      const error = {
        code: 'runtime_not_ready',
        message: 'The selected compute engine is not installed or is incompatible with the model'
      };
      managedRuntimeStore.update((current) => ({
        ...current,
        readiness,
        binding: null,
        lastError: error
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
    if (!selectedModel) throw trustPayloadError();
    const trustKind = modelTrustKind(selectedModel);
    const trustedStartEligible = trustKind === 'approved_catalog'
      && readiness.model_trust_kind === 'approved_catalog'
      && readiness.model_status === 'valid'
      && readiness.runtime_status === 'valid'
      && readiness.compatibility === 'compatible'
      && readiness.launchable === true;
    // Anti-freeze start: poll real backend phases while the supervisor works,
    // and cap the await with a watchdog slightly above the Rust
    // MODEL_LOAD_TIMEOUT. If the watchdog fires, the UI recovers truthfully and
    // a trailing refresh lets the store converge when the start settles later.
    const startPromise = trustedStartEligible
      ? startManagedRuntimeTrusted(state.selectedModelId, stillCurrent, requestedRuntimeId)
      : startManagedRuntime(
        state.selectedModelId,
        trustKind === 'user_supplied' ? selectedModel.asset_sha256 : stillCurrent,
        trustKind === 'user_supplied' ? stillCurrent : undefined,
        requestedRuntimeId
      );
    const progressTimer = setInterval(() => {
      if (!stillCurrent()) return;
      getManagedRuntimeStatus()
        .then((live) => {
          if (!stillCurrent()) return;
          managedRuntimeStore.update((current) => ({ ...current, status: live }));
        })
        .catch(() => undefined);
    }, MANAGED_START_PROGRESS_POLL_MS);
    let watchdogFired = false;
    let startFailed = false;
    let startError: unknown;
    let watchdogTimer: ReturnType<typeof setTimeout> | null = null;
    try {
      await Promise.race([
        startPromise,
        new Promise<never>((_, reject) => {
          watchdogTimer = setTimeout(() => {
            watchdogFired = true;
            reject({ code: 'start_watchdog_timeout', message: 'Managed runtime start exceeded the watchdog deadline' });
          }, MANAGED_START_WATCHDOG_MS);
        })
      ]);
    } catch (error) {
      startFailed = true;
      startError = error;
    } finally {
      clearInterval(progressTimer);
      if (watchdogTimer) clearTimeout(watchdogTimer);
    }
    if (watchdogFired) {
      if (stillCurrent()) {
        managedRuntimeStore.update((current) => ({
          ...current,
          lastError: normalizeGatewayError(startError)
        }));
      }
      // Do not retry or abandon the original start. Its eventual backend
      // result is observed once and converges the UI without spawning a second
      // runtime or losing the terminal error.
      void startPromise
        .then(() => {
          if (stillCurrent()) void refreshManagedRuntimeStatus().catch(() => undefined);
        })
        .catch((error) => {
          if (stillCurrent()) {
            managedRuntimeStore.update((current) => ({
              ...current,
              lastError: normalizeGatewayError(error)
            }));
            void refreshManagedRuntimeStatus().catch(() => undefined);
          }
        });
      return;
    }
    if (startFailed) throw startError;
    if (!stillCurrent()) {
      void refreshManagedRuntimeStatus();
      return;
    }
    const status = await getManagedRuntimeStatus();
    if (!stillCurrent()) {
      void refreshManagedRuntimeStatus();
      return;
    }
    managedRuntimeStore.update((current) => ({
      ...current,
      status,
      lastError:
        status.last_error &&
        !(!current.selectedModelId && /No managed model is selected/i.test(status.last_error))
          ? { code: 'runtime_unavailable', message: status.last_error }
          : null
    }));
    if (
      status.state === 'Ready' &&
      status.model_state === 'Ready' &&
      status.inference_ready === true &&
      status.model_id === state.selectedModelId &&
      typeof status.runtime_instance_id === 'string'
    ) {
      await confirmManagedBinding(readiness);
    }
  } catch (error) {
    if (!stillCurrent()) {
      void refreshManagedRuntimeStatus();
      return;
    }
    const normalized = normalizeGatewayError(error);
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalized }));
    clearManagedGatewayBinding();
    try {
      await refreshManagedRuntimeStatus();
    } catch {
      // Keep the normalized start error when the authoritative status endpoint
      // is unavailable; never turn a failed start into an apparently healthy
      // or indefinitely optimistic Starting state.
    }
    if (stillCurrent() && !get(managedRuntimeStore).lastError) {
      managedRuntimeStore.update((current) => ({ ...current, lastError: normalized }));
    }
  }
}

export async function stopSelectedManagedRuntime(): Promise<void> {
  await stopSelectedManagedRuntimeInternal(true);
}

async function stopSelectedManagedRuntimeInternal(invalidatePending: boolean): Promise<void> {
  if (invalidatePending) subscriptionGeneration += 1;
  const stateBeforeStop = get(managedRuntimeStore);
  const activeModelId = stateBeforeStop.status?.model_id ?? stateBeforeStop.selectedModelId;
  const activeModel = stateBeforeStop.catalog.find((model) => model.model_id === activeModelId);
  const trustedStopEligible = activeModel !== undefined
    && modelTrustKind(activeModel) === 'approved_catalog'
    && stateBeforeStop.installedArtifacts.some((artifact) =>
      artifact.kind === 'model' && artifact.artifact_id === activeModelId && artifact.installation_status === 'valid'
    )
    && activeModel.compatible_runtime_ids.some((runtimeId) =>
      stateBeforeStop.installedArtifacts.some((artifact) =>
        artifact.kind === 'runtime' && artifact.artifact_id === runtimeId && artifact.installation_status === 'valid'
      )
    );
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
    if (trustedStopEligible) {
      await stopManagedRuntimeTrusted();
    } else {
      await stopManagedRuntime();
    }
  } catch (error) {
    managedRuntimeStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
  }
  await refreshManagedRuntimeStatus();
}

export async function confirmManagedBinding(precomputedReadiness?: ModelReadinessSummary): Promise<void> {
  const generation = subscriptionGeneration;
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
  const stillCurrent = () => {
    const current = get(managedRuntimeStore);
    return generation === subscriptionGeneration &&
      current.selectedModelId === state.selectedModelId &&
      current.harnessId === state.harnessId &&
      current.status?.state === 'Ready' &&
      current.status.model_state === 'Ready' &&
      current.status.inference_ready === true &&
      current.status.model_id === state.selectedModelId &&
      current.status.runtime_instance_id === runtimeInstanceId;
  };
  const existing = state.binding;
  if (
    existing &&
    existing.provider_id === 'managed-llama-cpp' &&
    existing.harness_id === state.harnessId &&
    existing.model_id === state.selectedModelId &&
    existing.runtime_instance_id === runtimeInstanceId
  ) return;
  try {
    const readiness = precomputedReadiness ?? await readManagedModelReadiness(state.selectedModelId);
    if (generation !== subscriptionGeneration) return;
    if (!stillCurrent()) return;
    if (!readiness.launchable) {
      managedRuntimeStore.update((value) => ({ ...value, readiness, binding: null }));
      clearManagedGatewayBinding();
      return;
    }
    const binding = await setModelBinding({
      providerId: 'managed-llama-cpp',
      harnessId: state.harnessId,
      modelId: state.selectedModelId,
      runtimeInstanceId,
      isCurrent: stillCurrent
    });
    if (!stillCurrent()) return;
    managedRuntimeStore.update((value) => ({ ...value, readiness, binding, lastError: null }));
    modelGatewayStore.update((value) => ({ ...value, binding, status: 'Bound', lastError: null }));
  } catch (error) {
    if (!stillCurrent()) return;
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
  const generation = subscriptionGeneration;
  let state = get(managedRuntimeStore);
  const selectedModelId = state.selectedModelId;
  const harnessId = state.harnessId;
  const stillCurrent = () => generation === subscriptionGeneration &&
    get(managedRuntimeStore).selectedModelId === selectedModelId &&
    get(managedRuntimeStore).harnessId === harnessId;
  if (!selectedModelId) {
    managedRuntimeStore.update((current) => ({
      ...current,
      lastError: { code: 'model_not_selected', message: 'No managed model is selected' }
    }));
    return false;
  }
  try {
    const readiness = await readManagedModelReadiness(selectedModelId);
    if (!stillCurrent()) return false;
    managedRuntimeStore.update((current) => ({ ...current, readiness, lastError: null }));
    if (!readiness.launchable) {
      throw { code: 'model_not_ready', message: 'Managed model and runtime artifacts are not ready' };
    }

    state = get(managedRuntimeStore);
    const runningSelectedModel =
      state.status?.state === 'Ready' &&
      state.status.model_state === 'Ready' &&
      state.status.inference_ready === true &&
      state.status.model_id === state.selectedModelId;
    let runtimeWasStarted = false;
    if (!runningSelectedModel) {
      if (state.status?.state === 'Ready') await stopSelectedManagedRuntimeInternal(false);
      if (!stillCurrent()) return false;
      runtimeWasStarted = true;
      await startSelectedManagedRuntime(readiness);
      if (!stillCurrent()) return false;
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
    // startSelectedManagedRuntime already confirms the binding after a fresh
    // start. Confirm here only when the selected runtime was already running;
    // otherwise one click would create duplicate approval cards.
    if (!runtimeWasStarted) await confirmManagedBinding(readiness);
    if (!stillCurrent()) return false;
    return get(managedModelReady);
  } catch (error) {
    if (!stillCurrent()) return false;
    const normalized = normalizeGatewayError(error);
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalized }));
    clearManagedGatewayBinding();
    return false;
  }
}

export async function startLocalModelTurn(
  prompt: string,
  chatSessionId = DEFAULT_CONVERSATION_ID,
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
    const error = { code: 'model_not_ready', message: 'Managed model is not ready' };
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
  const effort = get(effortLevel);
  // A new turn revokes any launch continuation still running for an older
  // turn: a superseded continuation can never mutate cards or lifecycle.
  cancelComputerUseContinuations();
  clearInferenceTimers();
  bufferedEarlyEvents = [];
  inferenceRequestStore.set({
    lifecycle: 'submitted',
    requestId,
    chatSessionId,
    modelId: binding.model_id,
    effort,
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
  activeTurnPrompts.set(requestId, cleanPrompt);

  try {
    const messages = get(chatMessages).filter((message) =>
      message.conversationId === chatSessionId ||
      (!message.conversationId && chatSessionId === DEFAULT_CONVERSATION_ID)
    );
    const toolsEnabled = get(agentPermissions).tools;
    const initialSeedIds = new Set(['seed-user', 'seed-assistant']);
    const nonSeedMessages = messages.filter((m) => !initialSeedIds.has(m.id));
    // Long-conversation memory (audit P0): keep as much prior history as the
    // gateway accepts — GatewayLimits.maximum_messages (32) counts the system
    // message and the new prompt, and the harness byte cap is 2× prompt
    // (32 KiB). 14 messages × 2 KiB = 28 KiB fits with headroom; the oldest
    // entries drop off first and one oversized paste can't evict the window.
    const MAX_HISTORY_MESSAGES = 14;
    const MAX_HISTORY_MESSAGE_BYTES = 2_048;
    const historySlice = nonSeedMessages.slice(-MAX_HISTORY_MESSAGES);
    const recentMessages = historySlice.map((message) => {
      const content = (message.body || '').slice(0, MAX_HISTORY_MESSAGE_BYTES);
      if (message.role === 'assistant' && toolsEnabled && message.toolCalls && message.toolCalls.length > 0) {
        // The harness byte cap covers the SERIALIZED message, tool_calls
        // included. A tool-heavy turn (long command output echoed in a call)
        // can exceed 2 KiB by itself and kill every later turn with
        // payload_too_large. Drop the calls when the serialized entry no
        // longer fits; the text content stays.
        const withCalls = { role: message.role, content, tool_calls: message.toolCalls };
        if (JSON.stringify(withCalls).length <= MAX_HISTORY_MESSAGE_BYTES) {
          return withCalls;
        }
      }
      return { role: message.role, content };
    });
    const acceptance = await startModelTurn({
      requestId,
      chatSessionId,
      modelId: binding.model_id,
      submittedAtUnixMs,
      maxTokens: MODEL_REQUEST_MAX_TOKENS,
       seed: MODEL_REQUEST_SEED,
      effort,
      prompt: cleanPrompt,
      fileIds,
      // Interface chrome may be in any registered language, but the backend
      // only accepts ru | en for a turn, so map before sending.
      locale: assistantLocaleFor(get(locale)),
      bindingFingerprint: binding.binding_fingerprint,
      agentPermissions: get(agentPermissions),
      messages: recentMessages
    });

    if (acceptance.request_id !== requestId) throw new Error('Request ID mismatch');
    reportFilesContextInclusion(acceptance.file_context);
    const current = get(inferenceRequestStore);
    if (
      current.requestId !== requestId ||
      !['submitted', 'cancelling', 'cancelled'].includes(current.lifecycle)
    ) return false;
    clearInferenceTimer('acceptance');
    if (!appendAcceptedChatTurn(requestId, cleanPrompt, chatSessionId, effort)) {
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
    if (!cancelling) scheduleInferenceTimeout('firstToken', inferenceTimeoutsForCurrentBinding().firstToken, requestId);
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
    // Acceptance can fail before the reducer has created chat messages. Keep
    // the failed turn visible and retryable instead of leaving only a red
    // header badge and an orphaned composer draft.
    if (!get(chatMessages).some((message) => message.requestId === requestId)) {
      if (appendAcceptedChatTurn(requestId, cleanPrompt, chatSessionId, effort)) {
        setComposerDraft(cleanPrompt);
      }
    }
    terminalizeCurrentRequest('failed', 'model.turn.failed', normalized);
    return false;
  }
}

export async function cancelLocalModelTurn(): Promise<void> {
  await rejectActiveApproval();
  const current = get(inferenceRequestStore);
  const requestId = current.requestId;
  // Stop during a launch continuation revokes it: the bounded poll loop must
  // not mutate cards after the user cancelled the turn (plan P0.2).
  if (requestId) cancelComputerUseContinuations(requestId);
  if (!requestId || !['submitted', 'accepted', 'streaming', 'awaiting_approval', 'awaiting_verification'].includes(current.lifecycle)) return;
  // A launch_pending turn is still an active model turn: the UI is awaiting
  // host verification, but the sidecar worker remains cancellable. Do not
  // terminalize locally before the authoritative Rust acknowledgement; doing
  // so made Stop race the continuation lease and left no terminal proof.
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

export async function retryLocalModelTurn(requestId: string, chatSessionId = DEFAULT_CONVERSATION_ID): Promise<boolean> {
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
  if (isInferenceTerminal(current.lifecycle) || current.lifecycle === 'awaiting_verification') {
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

function enrichToolResultForPersistence(result: unknown, requestId: string, actionId: string): unknown {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return result;
  const payload = { ...(result as Record<string, unknown>) };
  // These IDs are already authenticated at the model-event boundary. Add them
  // only when the broker envelope omitted the optional display copy; preserve
  // any conflicting value so the harness and UI can still expose a mismatch.
  if (typeof payload.request_id !== 'string' || !payload.request_id) payload.request_id = requestId;
  if (typeof payload.action_id !== 'string' || !payload.action_id) payload.action_id = actionId;
  return payload;
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
    if (event.stream_channel === 'reasoning') {
      appendAssistantReasoningChunk(event.request_id, event.text);
    } else {
      appendAssistantChunk(event.request_id, event.text);
    }
    clearInferenceTimer('firstToken');
    scheduleInferenceTimeout('inactivity', inferenceTimeoutsForCurrentBinding().inactivity, event.request_id);
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
      generatedText: event.stream_channel === 'reasoning'
        ? state.generatedText
        : `${state.generatedText}${event.text}`.slice(0, MAX_GENERATED_TEXT)
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

  if (event.method === 'model.tool.request') {
    if (current.lifecycle === 'cancelling') return;
    if (event.tool_calls) {
      const modelCall = event.tool_calls[0];
      const originalPrompt = activeTurnPrompts.get(event.request_id);
      const browserSearchOverride = modelCall && originalPrompt
        ? deriveBoundedBrowserSearchContinuation(originalPrompt, modelCall)
        : null;
      // Some local models emit the initial browser open_app even though the
      // explicit guarded smoke prompt has a prevalidated read-only Python.org
      // navigation. Normalize only that exact shape before execution; the
      // original model action ID remains the correlation identity and the
      // replacement still goes through the ordinary Rust approval/broker path.
      const executionCall = browserSearchOverride && modelCall
        ? { ...browserSearchOverride, id: modelCall.id }
        : modelCall;
      const toolCalls = event.tool_calls.map((tc, index) => {
        const visibleCall = index === 0 && executionCall ? executionCall : tc;
        return {
          operation: visibleCall.name,
          target: stringifyForPersistence(visibleCall.arguments),
          status: 'WAITING' as const,
          elapsed: '-',
          detail: 'Tool execution requested',
          result: ''
        };
      });
      setAssistantToolCalls(event.request_id, toolCalls);
      inferenceRequestStore.update((state) => ({
        ...state,
        lifecycle: 'streaming',
        receivedContent: true
      }));

      // The sidecar emits the request before its terminal `tool_calls` event.
      // A tool call is no longer a model-token stream, so the response
      // watchdogs must not race the synchronous Rust -> sidecar execution.
      if (event.method === 'model.tool.request') {
        clearInferenceTimer('firstToken');
        clearInferenceTimer('inactivity');
        // Computer Use is dangerous in the Rust risk registry, so every action
        // must receive a scoped approval token before sidecar execution.
        const call = executionCall;
        if (!call) {
          terminalizeCurrentRequest('failed', 'model.turn.failed', {
            code: 'invalid_payload',
            message: 'Computer Use request contained no tool call'
          });
          return;
        }
        activeTurnCalls.set(event.request_id, call);
        const onResult = (result: unknown): void => {
          if (!canAcceptToolCallback(event.request_id)) return;
          const outcome = parseToolCallResult(call.name, result);
          const persistableResult = enrichToolResultForPersistence(result, event.request_id, call.id);
          if (outcome.kind === 'pending') {
            if (!canAcceptToolCallback(event.request_id)) return;
            // F-03: capture the one-time continuation capability FIRST, then
            // scrub the raw cgr_ token from the envelope before it is
            // stringified into chat card state or any persisted artifact.
            const continuationHandle = extractBrokerContinuationAndScrub(result);
            setAssistantToolCalls(event.request_id, toolCalls.map((item, index) =>
              index === 0 ? { ...item, status: 'WAITING' as const, result: stringifyForPersistence(persistableResult) } : item
            ));
            // launch_pending is never terminal success: the turn stops in the
            // truthful awaiting-verification state instead of claiming
            // completion over an unverified action.
            if (!canAcceptToolCallback(event.request_id)) return;
            terminalizeCurrentRequest('awaiting_verification', 'model.turn.completed');
            // Bounded continuation (plan P0.2): re-observe the recorded spawn
            // through cu_broker_observe - observation-only, no respawn, no new
            // token - until the broker reports a terminal envelope or its own
            // continuation TTL expires with an honest failed answer. When the
            // broker issued a typed continuation capability, the poll loop
            // consumes it once and completes it against the observed result.
            runBoundedLaunchContinuation(
              event.request_id,
              toolCalls[0],
              call.name,
              result,
              continuationHandle
            );
            return;
          }
          if (outcome.kind === 'blocked') {
            if (!canAcceptToolCallback(event.request_id)) return;
            setAssistantToolCalls(event.request_id, toolCalls.map((item, index) =>
              index === 0 ? { ...item, status: 'BLOCKED' as const, result: stringifyForPersistence(persistableResult) } : item
            ));
            terminalizeCurrentRequest('failed', 'model.turn.failed', {
              code: 'tool_execution_blocked',
              message: outcome.reason || 'tool action was blocked by policy'
            });
            return;
          }
          if (outcome.kind === 'failed' || outcome.kind === 'malformed') {
            if (!canAcceptToolCallback(event.request_id)) return;
            updateAssistantToolResult(
              event.request_id,
              0,
              'FAIL',
              outcome.reason || 'tool returned no confirmed success',
              outcome.reason || 'tool returned no confirmed success'
            );
            terminalizeCurrentRequest('failed', 'model.turn.failed', {
              code: outcome.kind === 'malformed' ? 'invalid_payload' : 'tool_execution_failed',
              message: outcome.reason || 'tool returned no confirmed success'
            });
            return;
          }
          if (outcome.kind === 'verified_success' && call.name === 'computer_use') {
            if (maybeStartBoundedNotepadTypeContinuation(event.request_id, toolCalls[0], call, result)) return;
            if (maybeStartBoundedBrowserSearchContinuation(event.request_id, toolCalls[0], call, result)) return;
          }
          if (outcome.kind === 'unverified_success' && call.name === 'computer_use') {
            if (!canAcceptToolCallback(event.request_id)) return;
            // Legacy adapter result (ok=true without the v1 envelope): at most
            // an unverified success - never a PASS pill or a completed turn.
            setAssistantToolCalls(event.request_id, toolCalls.map((item, index) =>
              index === 0 ? { ...item, status: 'UNVERIFIED' as const, result: stringifyForPersistence(persistableResult) } : item
            ));
            terminalizeCurrentRequest('awaiting_verification', 'model.turn.completed');
            return;
          }
          if (!canAcceptToolCallback(event.request_id)) return;
          setAssistantToolCalls(event.request_id, toolCalls.map((item, index) =>
            index === 0 ? { ...item, status: 'PASS' as const, result: stringifyForPersistence(persistableResult) } : item
          ));
          // Let Svelte mount the evidence-bearing ToolCallCard before terminal
          // lifecycle cleanup runs. A macrotask is required here: a microtask
          // can still run before the framework flushes the store update.
          setTimeout(() => {
            if (canAcceptToolCallback(event.request_id)) {
              terminalizeCurrentRequest('completed', 'model.turn.completed');
            }
          }, 0);
        };
        const onError = (error: unknown): void => {
          if (!canAcceptToolCallback(event.request_id)) return;
          const normalized = normalizeGatewayError(error);
          updateAssistantToolResult(event.request_id, 0, 'FAIL', normalized.message, normalized.message);
          terminalizeCurrentRequest('failed', 'model.turn.failed', normalized);
        };
        const readOnlyWorkspaceTool =
          (call.name === 'files.list' || call.name === 'files.read') &&
          get(agentPermissions).files &&
          get(workspaceStore).status === 'confirmed';
        if (readOnlyWorkspaceTool) {
          void runToolCall(call.name, call.arguments, undefined, call.id, event.request_id, call.id).then(onResult).catch(onError);
        } else {
          // Dangerous and guarded tools go through the approval flow so Rust
          // can mint and consume the scoped token. Keep the turn explicitly
          // busy while the modal is open; otherwise the composer says the
          // model is responding and allows a misleading second action.
          inferenceRequestStore.update((state) => ({
            ...state,
            lifecycle: 'awaiting_approval'
          }));
          modelGatewayStore.update((state) => ({ ...state, status: 'Awaiting approval' }));
          setApprovalCorrelation({ modelRequestId: event.request_id, modelActionId: call.id });
          requestApprovalForTool(call.name, call.arguments, {
            onResult,
            onError,
            requestId: event.request_id,
            actionId: call.id
          });
        }
        return;
      }
    }
  }

  // `model.turn.tool_calls` is an informational terminal event for the
  // current one-shot sidecar contract. It must not reinitialize the ToolCallCard
  // or be treated as a failed model turn after the authoritative request event.
  if (event.method === 'model.turn.tool_calls') return;

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

/**
 * Bounded observation continuation for a launch_pending computer_use spawn
 * (plan P0.2). Polls cu_broker_observe - which can never spawn or consume a
 * token - until the broker answers with a terminal envelope:
 *   verified_success -> PASS card + completed turn;
 *   failed/blocked   -> FAIL card + failed turn (incl. honest TTL expiry);
 *   still pending    -> bounded re-observe.
 * The loop is revoked by Stop/cancel/new-turn via the continuation registry;
 * a revoked or exhausted loop keeps the truthful awaiting-verification state
 * and never invents readiness.
 */
function maybeStartBoundedNotepadTypeContinuation(
  requestId: string,
  firstToolCard: import('$lib/data/mockData').ToolCallMock,
  firstCall: ModelToolCall,
  firstResult: unknown
): boolean {
  const originalPrompt = activeTurnPrompts.get(requestId);
  const derivedContinuation = originalPrompt
    ? deriveBoundedNotepadTypeContinuation(originalPrompt, firstCall)
    : null;
  if (!derivedContinuation) return false;
  let continuationCall: ModelToolCall;
  try {
    continuationCall = { ...derivedContinuation, id: createModelActionId() };
  } catch (error) {
    terminalizeCurrentRequest('failed', 'model.turn.failed', normalizeGatewayError(error));
    return true;
  }
  const current = get(inferenceRequestStore);
  if (current.requestId === requestId && current.lifecycle === 'awaiting_verification') {
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'streaming' }));
    modelGatewayStore.update((state) => ({ ...state, status: 'Generating' }));
  }
  startBoundedInteractionContinuation(
    requestId,
    firstToolCard,
    firstResult,
    continuationCall,
    'Bounded continuation requested after verified Notepad open'
  );
  return true;
}

function maybeStartBoundedBrowserSearchContinuation(
  requestId: string,
  firstToolCard: import('$lib/data/mockData').ToolCallMock,
  firstCall: ModelToolCall,
  firstResult: unknown
): boolean {
  const originalPrompt = activeTurnPrompts.get(requestId);
  const derivedContinuation = originalPrompt
    ? deriveBoundedBrowserSearchContinuation(originalPrompt, firstCall)
    : null;
  if (!derivedContinuation) return false;
  let continuationCall: ModelToolCall;
  try {
    continuationCall = { ...derivedContinuation, id: createModelActionId() };
  } catch (error) {
    terminalizeCurrentRequest('failed', 'model.turn.failed', normalizeGatewayError(error));
    return true;
  }
  const current = get(inferenceRequestStore);
  if (current.requestId === requestId && current.lifecycle === 'awaiting_verification') {
    inferenceRequestStore.update((state) => ({ ...state, lifecycle: 'streaming' }));
    modelGatewayStore.update((state) => ({ ...state, status: 'Generating' }));
  }
  startBoundedInteractionContinuation(
    requestId,
    firstToolCard,
    firstResult,
    continuationCall,
    'Bounded browser search requested after verified Chrome open'
  );
  return true;
}

function createModelActionId(): string {
  if (!globalThis.crypto?.getRandomValues) {
    throw { code: 'runtime_unavailable', message: 'Secure model action identifier generation is unavailable' };
  }
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return `call_${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

function startBoundedInteractionContinuation(
  requestId: string,
  firstToolCard: import('$lib/data/mockData').ToolCallMock,
  firstResult: unknown,
  continuationCall: ModelToolCall,
  continuationDetail: string
): void {
  const continuationToolCard: import('$lib/data/mockData').ToolCallMock = {
    operation: continuationCall.name,
    target: stringifyForPersistence(continuationCall.arguments),
    status: 'WAITING',
    elapsed: '-',
    detail: continuationDetail,
    result: ''
  };
  setAssistantToolCalls(requestId, [
    // F-03 defense in depth: no raw continuation secret can ride into card
    // state even if an upstream layer changes.
    {
      ...firstToolCard,
      status: 'PASS',
      result: stringifyForPersistence(firstResult)
    },
    continuationToolCard
  ]);

  const onContinuationResult = (rawResult: unknown): void => {
    if (!canAcceptToolCallback(requestId)) return;
    const outcome = parseToolCallResult(continuationCall.name, rawResult);
    if (outcome.kind === 'verified_success') {
      updateAssistantToolResult(requestId, 1, 'PASS', stringifyForPersistence(rawResult));
      terminalizeCurrentRequest('completed', 'model.turn.completed');
      return;
    }
    if (outcome.kind === 'blocked') {
      setAssistantToolCalls(requestId, [
        { ...firstToolCard, status: 'PASS', result: stringifyForPersistence(firstResult) },
        { ...continuationToolCard, status: 'BLOCKED', detail: outcome.reason || continuationToolCard.detail, result: stringifyForPersistence(rawResult) }
      ]);
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'tool_execution_blocked',
        message: outcome.reason || 'bounded continuation was blocked by policy'
      });
      return;
    }
    if (outcome.kind === 'pending') {
      setAssistantToolCalls(requestId, [
        { ...firstToolCard, status: 'PASS', result: stringifyForPersistence(firstResult) },
        { ...continuationToolCard, status: 'WAITING', detail: outcome.reason || continuationToolCard.detail, result: stringifyForPersistence(rawResult) }
      ]);
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'tool_execution_pending',
        message: outcome.reason || 'bounded continuation returned without terminal verification'
      });
      return;
    }
    if (outcome.kind === 'unverified_success') {
      setAssistantToolCalls(requestId, [
        { ...firstToolCard, status: 'PASS', result: stringifyForPersistence(firstResult) },
        { ...continuationToolCard, status: 'UNVERIFIED', detail: outcome.reason || continuationToolCard.detail, result: stringifyForPersistence(rawResult) }
      ]);
    } else {
      setAssistantToolCalls(requestId, [
        { ...firstToolCard, status: 'PASS', result: stringifyForPersistence(firstResult) },
        { ...continuationToolCard, status: 'FAIL', detail: outcome.reason || continuationToolCard.detail, result: stringifyForPersistence(rawResult) }
      ]);
    }
    terminalizeCurrentRequest(
      outcome.kind === 'unverified_success' ? 'awaiting_verification' : 'failed',
      outcome.kind === 'unverified_success' ? 'model.turn.completed' : 'model.turn.failed',
      outcome.kind === 'unverified_success' ? null : {
        code: outcome.kind === 'malformed' ? 'invalid_payload' : 'tool_execution_failed',
        message: outcome.reason || 'bounded continuation failed'
      }
    );
  };
  const onContinuationError = (error: unknown): void => {
    if (!canAcceptToolCallback(requestId)) return;
    const normalized = normalizeGatewayError(error);
    setAssistantToolCalls(requestId, [
      { ...firstToolCard, status: 'PASS', result: stringifyForPersistence(firstResult) },
      { ...continuationToolCard, status: 'FAIL', detail: normalized.message, result: normalized.message }
    ]);
    terminalizeCurrentRequest('failed', 'model.turn.failed', normalized);
  };

  // Defer until the first approval callback has returned. This prevents the
  // approval store's first-flow cleanup from clearing the second flow state.
  queueMicrotask(() => {
    if (!canAcceptToolCallback(requestId)) return;
    setApprovalCorrelation({ modelRequestId: requestId, modelActionId: continuationCall.id });
    requestApprovalForTool(continuationCall.name, continuationCall.arguments, {
      onResult: onContinuationResult,
      onError: onContinuationError,
      requestId,
      actionId: continuationCall.id
    });
  });
}

function runBoundedLaunchContinuation(
  requestId: string,
  toolCall: import('$lib/data/mockData').ToolCallMock,
  toolName: string,
  launchEnvelope?: unknown,
  // F-03: the raw grant never travels through the envelope copy that reaches
  // UI state; the caller captures it via extractBrokerContinuationAndScrub
  // and hands over this in-memory-only handle instead.
  continuationHandle?: BrokerContinuationHandle | null
): void {
  activeContinuationRequests.add(requestId);
  let attempts = 0;
  // Typed continuation capability issued by the Rust broker (master prompt
  // Part I). Only the opaque handle is held in bounded in-memory state; it is
  // never logged or persisted. task/step correlation must match the Rust
  // issuance exactly: task_{request_id} / step_{action_id}.
  let continuation: BrokerContinuationHandle | null = continuationHandle ?? null;
  if (!continuation && launchEnvelope) {
    // Defensive fallback for legacy call sites: capture + scrub in one step.
    const scrubbed = extractBrokerContinuationAndScrub(launchEnvelope);
    if (scrubbed) {
      redactGrantRefsInPlace(launchEnvelope);
      continuation = scrubbed;
    }
  }
  const actionId = activeTurnCalls.get(requestId)?.id ?? '';
  let leaseId: string | null = null;
  // The exact consume arguments are kept (in-memory only) so cancellation can
  // replay the identical consume through the real broker and prove the revoked
  // grant rejects it (B3). The map wrapper is the single holder of the raw
  // material; the replay probe clears it right after settling.
  let consumeArgs: Record<string, unknown> | null = null;
  if (continuation) {
    consumeArgs = {
      grantRef: continuation.grantRef,
      taskId: `task_${requestId}`,
      stepId: `step_${actionId}`,
      requestId,
      actionKind: 'observe',
      input: { action: 'observe' },
      expectedStepIndex: continuation.stepIndex + 1
    };
    activeContinuationGrants.set(requestId, { grantRef: continuation.grantRef, consumeArgs });
    recordContinuationTrace({
      event: 'continuation_issued',
      request_id: requestId,
      status: 'issued'
    });
  }

  // Re-lease the broker grant, or no-op when a lease is already held (the
  // Rust grant is one-time; an in_flight grant must not be re-consumed).
  const consumeGrant = (): Promise<string | null> => {
    if (!continuation || leaseId || !consumeArgs) return Promise.resolve(leaseId);
    recordContinuationTrace({ event: 'continuation_consume_requested', request_id: requestId });
    return invoke('cu_broker_continuation_consume', consumeArgs)
      .then((raw) => {
        const lease = raw as { status?: string; lease_id?: string };
        if (lease?.status === 'leased' && typeof lease.lease_id === 'string') {
          leaseId = lease.lease_id;
          recordContinuationTrace({ event: 'continuation_consume_leased', request_id: requestId, status: 'leased' });
          return leaseId;
        }
        recordContinuationTrace({ event: 'continuation_consume_rejected', request_id: requestId });
        return null;
      })
      .catch((error) => {
        recordContinuationTrace({ event: 'continuation_consume_failed', request_id: requestId, error_code: continuationErrorCode(error) });
        return null;
      });
  };

  const completeGrant = (status: 'verified' | 'failed' | 'blocked' | 'pending', verified: boolean): void => {
    if (!leaseId) return;
    const currentLease = leaseId;
    recordContinuationTrace({ event: 'continuation_complete_requested', request_id: requestId, status });
    invoke('cu_broker_continuation_complete', {
      leaseId: currentLease,
      status,
      postconditionVerified: verified
    }).then(() => {
      // Release the lease only after the host accepted the completion; on failure
      // the lease stays usable until its Rust-side TTL (30s) expires.
      if (leaseId === currentLease) leaseId = null;
      recordContinuationTrace({ event: 'continuation_complete_succeeded', request_id: requestId, status });
    }).catch((error) => {
      recordContinuationTrace({ event: 'continuation_complete_failed', request_id: requestId, status, error_code: continuationErrorCode(error) });
    });
  };
  const finish = (status: 'PASS' | 'FAIL', envelope: Record<string, unknown>, lifecycle: 'completed' | 'failed'): void => {
    activeContinuationRequests.delete(requestId);
    if (!isActiveInferenceRequest(requestId)) return;
    setAssistantToolCalls(requestId, [{ ...toolCall, status, result: stringifyForPersistence(envelope) }]);
    if (lifecycle === 'completed') {
      terminalizeCurrentRequest('completed', 'model.turn.completed');
    } else {
      const reason = typeof envelope.reason === 'string' ? envelope.reason : 'continuation observed failure';
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'tool_execution_failed',
        message: reason
      });
    }
  };
  const tick = (): void => {
    // Revoked by Stop/reject/reload/new-turn (see cancelComputerUseContinuations):
    // keep only the truthful pending state while the grant is being revoked.
    if (!activeContinuationRequests.has(requestId) || !isActiveInferenceRequest(requestId)) {
      cancelComputerUseContinuations(requestId);
      activeContinuationRequests.delete(requestId);
      return;
    }
    attempts += 1;
    if (attempts > CONTINUATION_MAX_ATTEMPTS) {
      cancelComputerUseContinuations(requestId);
      activeContinuationRequests.delete(requestId);
      // Honest local expiry (broker TTL should have answered first).
      setAssistantToolCalls(requestId, [{
        ...toolCall,
        status: 'FAIL' as const,
        result: JSON.stringify({
          status: 'failed',
          reason: 'launch continuation window expired without observed readiness'
        })
      }]);
      terminalizeCurrentRequest('failed', 'model.turn.failed', {
        code: 'tool_execution_failed',
        message: 'launch continuation expired without verified readiness'
      });
      return;
    }
    consumeGrant()
      .then(() => {
        if (!activeContinuationRequests.has(requestId)) return undefined;
        recordContinuationTrace({ event: 'continuation_observe_requested', request_id: requestId });
        return invoke('cu_broker_observe', { requestId }) as Promise<unknown>;
      })
      .then((raw) => {
        if (!raw || !activeContinuationRequests.has(requestId)) return;
        const res = raw as { found: boolean; envelope?: Record<string, unknown> };
        recordContinuationTrace({ event: 'continuation_observe_result', request_id: requestId, found: res.found === true });
        if (!res?.found || !res.envelope) {
          scheduleNextTick();
          return;
        }
        const outcome = parseToolCallResult(toolName, res.envelope);
        if (outcome.kind === 'verified_success') {
          const firstCall = activeTurnCalls.get(requestId);
          if (firstCall && maybeStartBoundedNotepadTypeContinuation(requestId, toolCall, firstCall, res.envelope)) {
            completeGrant('verified', true);
            activeContinuationRequests.delete(requestId);
            return;
          }
          if (firstCall && maybeStartBoundedBrowserSearchContinuation(requestId, toolCall, firstCall, res.envelope)) {
            completeGrant('verified', true);
            activeContinuationRequests.delete(requestId);
            return;
          }
          completeGrant('verified', true);
          finish('PASS', res.envelope, 'completed');
        } else if (outcome.kind === 'failed' || outcome.kind === 'blocked') {
          completeGrant(outcome.kind === 'blocked' ? 'blocked' : 'failed', false);
          finish('FAIL', res.envelope, 'failed');
        } else {
          // Still pending -> re-arm the one-time grant for the next bounded
          // observation; card stays WAITING/truthful.
          completeGrant('pending', false);
          scheduleNextTick();
        }
      })
      .catch(() => {
        // Infrastructure miss keeps the truthful pending card and retries
        // within the same bound.
        if (activeContinuationRequests.has(requestId)) {
          scheduleNextTick();
        }
      });
  };
  const scheduleNextTick = (): void => {
    setTimeout(() => {
      tick();
    }, CONTINUATION_POLL_INTERVAL_MS);
  };
  setTimeout(() => {
    tick();
  }, CONTINUATION_FIRST_CHECK_MS);
}

function terminalizeCurrentRequest(
  lifecycle: 'completed' | 'awaiting_verification' | 'cancelled' | 'timed_out' | 'failed',
  method: ModelGatewayEvent['method'],
  error: SanitizedGatewayError | null = null
): boolean {
  const current = get(inferenceRequestStore);
  // Any terminal transition revokes a still-running launch continuation so
  // timeouts/protocol failures/cancellations cannot race the poll loop.
  if (current.requestId) cancelComputerUseContinuations(current.requestId);
  if (lifecycle !== 'awaiting_verification' && current.requestId) {
    activeTurnPrompts.delete(current.requestId);
    activeTurnCalls.delete(current.requestId);
  }
  // awaiting_verification is TRANSIENT (plan P0.2/P1.3): it must stay busy
  // for composers/timers, yet always allow an authoritative move into
  // completed/failed/cancelled — otherwise a verified launch could never be
  // published and Stop during verification silently did nothing.
  const blocked = !current.requestId || isInferenceTerminal(current.lifecycle);
  if (blocked) return false;
  clearInferenceTimers();
  bufferedEarlyEvents = [];
  finalizeAssistantMessage(current.requestId, lifecycle, error ? `${error.code}: ${error.message}` : undefined);
  inferenceRequestStore.set({
    ...current,
    lifecycle,
    terminalAtUnixMs: Date.now(),
    terminalMethod: method,
    lastError: error
  });
  modelGatewayStore.update((state) => ({
    ...state,
    status: lifecycle === 'completed'
      ? 'Completed'
      : lifecycle === 'awaiting_verification'
        ? 'Pending verification'
        : lifecycle === 'cancelled'
          ? 'Cancelled'
          : 'Failed',
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

function inferenceTimeoutsForCurrentBinding() {
  return get(modelGatewayStore).binding?.provider_id === 'managed-llama-cpp'
    ? { ...INFERENCE_TIMEOUTS_MS, ...MANAGED_INFERENCE_TIMEOUTS_MS }
    : INFERENCE_TIMEOUTS_MS;
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

export function isActiveInferenceRequest(requestId: string): boolean {
  return requestId.length > 0 && get(inferenceRequestStore).requestId === requestId;
}

export function canAcceptToolCallback(requestId: string): boolean {
  const current = get(inferenceRequestStore);
  return isActiveInferenceRequest(requestId) &&
    !isInferenceTerminal(current.lifecycle) &&
    current.lifecycle !== 'awaiting_verification' &&
    current.lifecycle !== 'cancelling';
}

export function isInferenceTerminal(lifecycle: InferenceRequestState['lifecycle']): boolean {
  // awaiting_verification is deliberately transient: the broker continuation
  // may still publish an authoritative completed/failed outcome.
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
  const trustKind = modelTrustKind(model);
  if (trustKind === 'approved_catalog') assertSameCatalogIdentity(identity, readiness);
  if (
    readiness.model_trust_kind !== trustKind ||
    !sameStrings(readiness.compatible_runtime_ids, model.compatible_runtime_ids)
  ) throw trustPayloadError();
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
  const customModels = new Map(modelCatalog.custom_models.map((model) => [model.model_id, model] as const));
  for (const model of [...modelCatalog.models, ...modelCatalog.custom_models]) {
    if (model.compatible_runtime_ids.some((runtimeId) => !runtimes.has(runtimeId))) throw trustPayloadError();
  }
  if (installedArtifacts.artifacts.length !== runtimes.size + models.size) throw trustPayloadError();
  for (const artifact of installedArtifacts.artifacts) {
    const approved = artifact.kind === 'runtime' ? runtimes.get(artifact.artifact_id) : models.get(artifact.artifact_id);
    if (!approved || approved.status !== artifact.catalog_status) throw trustPayloadError();
    
    const approvedBytes = 'archive_bytes' in approved ? approved.archive_bytes : approved.asset_bytes;
    const approvedSha256 = 'archive_sha256' in approved ? approved.archive_sha256 : approved.asset_sha256;
    
    if (
      approvedBytes !== artifact.expected_bytes ||
      approvedSha256 !== artifact.expected_sha256
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

function selectStrongestInstalledManagedModelId(
  models: readonly (ManagedModelSummary | ApprovedModelSummary)[],
  runtimes: readonly ApprovedRuntimeSummary[],
  installedArtifacts: readonly ManagedArtifactValidationSummary[]
): string {
  // Selection is intentionally fail-closed. A missing or invalid pinned
  // baseline must stop setup rather than silently launching another model.
  const preferred = models.find((model) => model.model_id === DEFAULT_BASE_MODEL_ID);
  return preferred && isInstalledLaunchable(preferred, runtimes, installedArtifacts)
    ? preferred.model_id
    : '';
}
function selectPreferredInstalledManagedRuntimeId(
  model: ManagedModelSummary | ApprovedModelSummary,
  runtimes: readonly ApprovedRuntimeSummary[],
  installedArtifacts: readonly ManagedArtifactValidationSummary[],
  fallbackRuntimeId: string | null | undefined
): string | null {
  const compatibleInstalledRuntimes = runtimes.filter((runtime) =>
    model.compatible_runtime_ids.includes(runtime.runtime_id) &&
    installedArtifacts.some((artifact) =>
      artifact.kind === 'runtime' &&
      artifact.artifact_id === runtime.runtime_id &&
      artifact.installation_status === 'valid'
    )
  );
  return compatibleInstalledRuntimes.find((runtime) => runtime.variant === 'vulkan')?.runtime_id
    ?? compatibleInstalledRuntimes.find((runtime) => runtime.runtime_id === fallbackRuntimeId)?.runtime_id
    ?? compatibleInstalledRuntimes[0]?.runtime_id
    ?? null;
}

function isInstalledLaunchable(
  model: ManagedModelSummary | ApprovedModelSummary,
  runtimes: readonly ApprovedRuntimeSummary[],
  installedArtifacts: readonly ManagedArtifactValidationSummary[]
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
  const selectedModel = managed.catalog.find((model) => model.model_id === selectedModelId);
  if (
    !selectedModelId ||
    !selectedModel ||
    !status ||
    status.state !== 'Ready' ||
    status.model_state !== 'Ready' ||
    status.inference_ready !== true ||
    status.model_id !== selectedModelId ||
    !status.runtime_instance_id ||
    !status.binding_fingerprint ||
    !readiness ||
    readiness.model_id !== selectedModelId ||
    (readiness.model_trust_kind ?? 'approved_catalog') !== modelTrustKind(selectedModel) ||
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

function modelTrustKind(model: ManagedModelSummary | ApprovedModelSummary): ModelReadinessSummary['model_trust_kind'] {
  return 'trust_kind' in model ? model.trust_kind : 'approved_catalog';
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
