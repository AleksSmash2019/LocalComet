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
  finalizeAssistantMessage,
  setModelConnected
} from '$lib/stores/shellStore';
import { locale } from '$lib/i18n';

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

export async function startSelectedManagedRuntime(): Promise<void> {
  const state = get(managedRuntimeStore);
  if (!state.selectedModelId) return;
  try {
    const readiness = await readManagedModelReadiness(state.selectedModelId);
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
    await refreshManagedRuntimeStatus();
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

export async function confirmManagedBinding(): Promise<void> {
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
    const readiness = await readManagedModelReadiness(state.selectedModelId);
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

export async function connectSelectedManagedModel(): Promise<boolean> {
  let state = get(managedRuntimeStore);
  if (!state.selectedModelId) return false;
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
      await startSelectedManagedRuntime();
    }

    state = get(managedRuntimeStore);
    if (
      state.status?.state !== 'Ready' ||
      state.status.model_state !== 'Ready' ||
      state.status.inference_ready !== true ||
      state.status.model_id !== state.selectedModelId
    ) return false;
    await confirmManagedBinding();
    return get(managedModelReady);
  } catch (error) {
    const normalized = normalizeGatewayError(error);
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalized }));
    clearManagedGatewayBinding();
    return false;
  }
}

export async function startLocalModelTurn(prompt: string, chatSessionId = 'local-chat'): Promise<boolean> {
  const cleanPrompt = prompt.slice(0, 12_000).trim();
  if (!cleanPrompt || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(chatSessionId)) return false;
  if (submissionInProgress || get(inferenceBusy)) return false;
  submissionInProgress = true;
  try {
    return await startClaimedLocalModelTurn(cleanPrompt, chatSessionId);
  } finally {
    submissionInProgress = false;
  }
}

async function startClaimedLocalModelTurn(cleanPrompt: string, chatSessionId: string): Promise<boolean> {
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
    await startModelTurn({
      requestId,
      chatSessionId,
      modelId: binding.model_id,
      submittedAtUnixMs,
      maxTokens: MODEL_REQUEST_MAX_TOKENS,
      prompt: cleanPrompt,
      locale: get(locale),
      bindingFingerprint: binding.binding_fingerprint
    });
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
  inferenceRequestStore.set(initialInferenceState);
}

function currentPort(): number {
  const value = Number(get(modelGatewayStore).portText);
  if (!Number.isInteger(value) || value < 1024 || value > 65535) {
    throw { code: 'invalid_payload', message: 'Port must be 1024-65535' };
  }
  return value;
}
