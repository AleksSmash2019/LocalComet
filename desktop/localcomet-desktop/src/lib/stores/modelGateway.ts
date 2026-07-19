import { get, writable } from 'svelte/store';
import {
  cancelModelTurn,
  getManagedModelCatalog,
  getManagedRuntimeLogs,
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
  GatewayCatalog,
  GatewayStatus,
  HarnessId,
  ManagedModelEntry,
  ManagedRuntimeLogs,
  ManagedRuntimeState,
  ManagedRuntimeStatus,
  ModelBinding,
  ModelGatewayEvent,
  ModelSummary,
  SanitizedGatewayError
} from '$lib/types/modelGateway';

export const MAX_GENERATED_TEXT = 262_144;

interface ModelGatewayState {
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

interface ManagedRuntimePanelState {
  readonly status: ManagedRuntimeStatus | null;
  readonly catalog: readonly ManagedModelEntry[];
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
  catalog: [],
  selectedModelId: '',
  harnessId: 'minimal',
  binding: null,
  logs: { stdout_tail: [], stderr_tail: [] },
  lastError: null
};

let unsubscribeEvents: (() => void) | null = null;
let initialized = false;
const lastSequenceByTurn = new Map<string, number>();

export const modelGatewayStore = writable<ModelGatewayState>(initialState);
export const managedRuntimeStore = writable<ManagedRuntimePanelState>(initialManagedState);

export async function initializeModelGateway(): Promise<void> {
  if (initialized) return;
  initialized = true;
  try {
    unsubscribeEvents = await subscribeModelGatewayEvents(applyModelGatewayEvent);
    const catalog = await getModelGatewayCatalog();
    modelGatewayStore.update((state) => ({ ...state, catalog, initialized: true, status: 'Binding required' }));
    await refreshManagedRuntimeStatus();
  } catch (error) {
    modelGatewayStore.update((state) => ({ ...state, initialized: true, status: 'Unavailable', lastError: normalizeGatewayError(error) }));
  }
}

export function shutdownModelGateway(): void {
  unsubscribeEvents?.();
  unsubscribeEvents = null;
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

export function setManagedSelectedModel(modelId: string): void {
  managedRuntimeStore.update((state) => ({
    ...state,
    selectedModelId: modelId,
    binding: state.binding?.model_id === modelId ? state.binding : null
  }));
}

export function setManagedHarness(harnessId: HarnessId): void {
  managedRuntimeStore.update((state) => ({
    ...state,
    harnessId,
    binding: state.binding?.harness_id === harnessId ? state.binding : null
  }));
}

export async function refreshManagedRuntimeStatus(): Promise<void> {
  try {
    const [status, catalog, logs] = await Promise.all([
      getManagedRuntimeStatus(),
      getManagedModelCatalog().catch(() => ({ models: [] })),
      getManagedRuntimeLogs().catch(() => ({ stdout_tail: [], stderr_tail: [] }))
    ]);
    managedRuntimeStore.update((state) => ({
      ...state,
      status,
      catalog: 'models' in catalog ? catalog.models : [],
      logs,
      lastError: null,
      binding: status.state === 'Ready' ? state.binding : null
    }));
  } catch (error) {
    managedRuntimeStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
  }
}

export async function startSelectedManagedRuntime(): Promise<void> {
  const state = get(managedRuntimeStore);
  if (!state.selectedModelId) return;
  managedRuntimeStore.update((current) => ({
    ...current,
    status: current.status ? { ...current.status, state: 'Starting' as ManagedRuntimeState } : current.status,
    lastError: null
  }));
  try {
    await startManagedRuntime(state.selectedModelId);
    await refreshManagedRuntimeStatus();
  } catch (error) {
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalizeGatewayError(error) }));
    await refreshManagedRuntimeStatus();
  }
}

export async function stopSelectedManagedRuntime(): Promise<void> {
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
  if (!state.selectedModelId || !runtimeInstanceId || state.status?.state !== 'Ready') return;
  try {
    const binding = await setModelBinding({
      providerId: 'managed-llama-cpp',
      harnessId: state.harnessId,
      modelId: state.selectedModelId,
      runtimeInstanceId
    });
    managedRuntimeStore.update((current) => ({ ...current, binding, lastError: null }));
    modelGatewayStore.update((current) => ({ ...current, binding, status: 'Bound', lastError: null }));
  } catch (error) {
    managedRuntimeStore.update((current) => ({ ...current, binding: null, lastError: normalizeGatewayError(error) }));
  }
}

export async function startLocalModelTurn(prompt: string): Promise<void> {
  const binding = get(modelGatewayStore).binding;
  if (!binding) {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    return;
  }
  try {
    const started = await startModelTurn(prompt, binding.binding_fingerprint);
    modelGatewayStore.update((state) => ({
      ...state,
      status: 'Generating',
      activeTurnId: started.turn_id,
      generatedText: '',
      modelCalled: false,
      toolsExecuted: 0,
      persistence: 'Off',
      lastError: null
    }));
  } catch (error) {
    modelGatewayStore.update((state) => ({ ...state, status: 'Failed', lastError: normalizeGatewayError(error) }));
  }
}

export async function cancelLocalModelTurn(): Promise<void> {
  const turnId = get(modelGatewayStore).activeTurnId;
  if (!turnId) return;
  modelGatewayStore.update((state) => ({ ...state, status: 'Cancelling' }));
  try {
    await cancelModelTurn(turnId);
  } catch (error) {
    modelGatewayStore.update((state) => ({ ...state, status: 'Failed', lastError: normalizeGatewayError(error) }));
  }
}

export function applyModelGatewayEvent(event: ModelGatewayEvent): void {
  const last = lastSequenceByTurn.get(event.turn_id);
  if (last !== undefined && event.sequence <= last) return;
  lastSequenceByTurn.set(event.turn_id, event.sequence);
  modelGatewayStore.update((state) => {
    if (state.activeTurnId && event.turn_id !== state.activeTurnId) return state;
    if (['Completed', 'Cancelled', 'Failed'].includes(state.status) && event.method === 'model.output.delta') return state;
    if (event.method === 'model.output.delta') {
      return {
        ...state,
        status: 'Generating',
        modelCalled: event.model_called,
        generatedText: `${state.generatedText}${event.text ?? ''}`.slice(0, MAX_GENERATED_TEXT)
      };
    }
    if (event.method === 'model.turn.started') {
      return { ...state, status: 'Generating', modelCalled: event.model_called, activeTurnId: event.turn_id };
    }
    if (event.method === 'model.turn.completed') {
      return { ...state, status: 'Completed', modelCalled: event.model_called, activeTurnId: null };
    }
    if (event.method === 'model.turn.cancelled') {
      return { ...state, status: 'Cancelled', modelCalled: event.model_called, activeTurnId: null };
    }
    if (event.method === 'model.turn.failed') {
      return {
        ...state,
        status: 'Failed',
        activeTurnId: null,
        lastError: event.error ? { code: event.error.code, message: event.error.message } : state.lastError
      };
    }
    return state;
  });
}

export function resetModelGatewayStore(): void {
  initialized = false;
  unsubscribeEvents = null;
  lastSequenceByTurn.clear();
  modelGatewayStore.set(initialState);
  managedRuntimeStore.set(initialManagedState);
}

function currentPort(): number {
  const value = Number(get(modelGatewayStore).portText);
  if (!Number.isInteger(value) || value < 1024 || value > 65535) {
    throw { code: 'invalid_payload', message: 'Port must be 1024-65535' };
  }
  return value;
}
