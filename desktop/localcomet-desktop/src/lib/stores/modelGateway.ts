import { get, writable } from 'svelte/store';
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
    const selectedModelId = modelCatalog.models.some((model) => model.model_id === previous.selectedModelId)
      ? previous.selectedModelId
      : '';
    const selectedModel = modelCatalog.models.find((model) => model.model_id === selectedModelId);
    const bindingTrusted =
      status.state === 'Ready' &&
      previous.binding !== null &&
      previous.binding.model_id === selectedModelId &&
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
      status: current.status ? { ...current.status, state: 'Starting' as ManagedRuntimeState } : current.status,
      lastError: null
    }));
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
  if (!state.selectedModelId || !runtimeInstanceId || state.status?.state !== 'Ready' || !state.readiness?.launchable) return;
  try {
    const readiness = await readManagedModelReadiness(state.selectedModelId);
    const current = get(managedRuntimeStore);
    if (!readiness.launchable || current.selectedModelId !== state.selectedModelId || current.harnessId !== state.harnessId) {
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
