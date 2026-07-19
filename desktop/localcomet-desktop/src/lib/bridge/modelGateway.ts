import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type {
  GatewayCatalog,
  HarnessId,
  ManagedModelCatalog,
  ManagedRuntimeLogs,
  ManagedRuntimeStartResponse,
  ManagedRuntimeStatus,
  ModelBinding,
  ModelGatewayEvent,
  ModelListResponse,
  ModelTurnStartResponse,
  ProbeResponse,
  ProviderId,
  SanitizedGatewayError
} from '$lib/types/modelGateway';
import { CONTROL_PLANE_EVENT_CHANNEL } from './controlPlane';

type InvokeArgs = Readonly<Record<string, string | number | boolean>>;

export async function getModelGatewayCatalog(): Promise<GatewayCatalog> {
  return validateCatalog(await invokeExact('model_gateway_catalog'));
}

export async function probeModelGateway(port: number): Promise<ProbeResponse> {
  return validateProbe(await invokeExact('model_gateway_probe', { port: validatePort(port) }));
}

export async function listModelGatewayModels(port: number): Promise<ModelListResponse> {
  return validateModels(await invokeExact('model_gateway_list_models', { port: validatePort(port) }));
}

export async function setModelBinding(args: {
  providerId: ProviderId;
  harnessId: HarnessId;
  port?: number;
  modelId: string;
  runtimeInstanceId?: string;
}): Promise<ModelBinding> {
  const invokeArgs: Record<string, string | number | boolean> = {
    providerId: args.providerId,
    harnessId: args.harnessId,
    modelId: validateModelId(args.modelId),
    confirmed: true
  };
  if (args.providerId === 'openai-compatible-local') {
    invokeArgs.port = validatePort(Number(args.port));
  }
  if (args.runtimeInstanceId) {
    invokeArgs.runtimeInstanceId = args.runtimeInstanceId;
  }
  return validateBinding(
    await invokeExact('model_binding_set', invokeArgs)
  );
}

export async function getManagedRuntimeStatus(): Promise<ManagedRuntimeStatus> {
  return validateManagedStatus(await invokeExact('managed_runtime_status'));
}

export async function getManagedModelCatalog(): Promise<ManagedModelCatalog> {
  return validateManagedCatalog(await invokeExact('managed_model_catalog'));
}

export async function startManagedRuntime(modelId: string): Promise<ManagedRuntimeStartResponse> {
  return validateManagedStart(await invokeExact('managed_runtime_start', { modelId: validateModelId(modelId) }));
}

export async function stopManagedRuntime(): Promise<void> {
  await invokeExact('managed_runtime_stop');
}

export async function getManagedRuntimeLogs(): Promise<ManagedRuntimeLogs> {
  return validateManagedLogs(await invokeExact('managed_runtime_logs'));
}

export async function startModelTurn(prompt: string, bindingFingerprint: string): Promise<ModelTurnStartResponse> {
  return validateTurnStart(
    await invokeExact('model_turn_start', {
      prompt: bounded(prompt, 16_384),
      bindingFingerprint: validateFingerprint(bindingFingerprint)
    })
  );
}

export async function cancelModelTurn(turnId: string): Promise<void> {
  await invokeExact('model_turn_cancel', { turnId: validateTurnId(turnId) });
}

export async function subscribeModelGatewayEvents(callback: (event: ModelGatewayEvent) => void): Promise<() => void> {
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    const parsed = parseModelEvent(event.payload);
    if (parsed) callback(parsed);
  });
  return () => cleanup();
}

export function normalizeGatewayError(error: unknown): SanitizedGatewayError {
  if (isRecord(error)) {
    return {
      code: bounded(typeof error.code === 'string' ? error.code : 'gateway_error', 64),
      message: bounded(sanitize(typeof error.message === 'string' ? error.message : 'Local model gateway error'), 240)
    };
  }
  return { code: 'gateway_error', message: 'Local model gateway error' };
}

async function invokeExact<T>(command: string, args?: InvokeArgs): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw normalizeGatewayError(error);
  }
}

function validateCatalog(value: unknown): GatewayCatalog {
  const object = expectRecord(value);
  if (!Array.isArray(object.providers) || !Array.isArray(object.harnesses)) throw invalid();
  const providers = object.providers.map(expectRecord);
  const harnesses = object.harnesses.map(expectRecord);
  if (providers.map((item) => item.provider_id).join('|') !== 'openai-compatible-local|managed-llama-cpp') throw invalid();
  if (harnesses.map((item) => item.harness_id).join('|') !== 'minimal|native-localcomet') throw invalid();
  return object as unknown as GatewayCatalog;
}

function validateProbe(value: unknown): ProbeResponse {
  const object = expectRecord(value);
  if (object.provider_id !== 'openai-compatible-local' || object.host !== '127.0.0.1' || object.base_path !== '/v1') throw invalid();
  validatePort(Number(object.port));
  return object as unknown as ProbeResponse;
}

function validateModels(value: unknown): ModelListResponse {
  const object = expectRecord(value);
  if (object.provider_id !== 'openai-compatible-local' || object.host !== '127.0.0.1' || !Array.isArray(object.models)) throw invalid();
  object.models.forEach((item) => validateModelId(String(expectRecord(item).model_id)));
  return object as unknown as ModelListResponse;
}

function validateBinding(value: unknown): ModelBinding {
  const object = expectRecord(value);
  if (!['openai-compatible-local', 'managed-llama-cpp'].includes(String(object.provider_id)) || object.persistence !== false) throw invalid();
  if (object.provider_id === 'openai-compatible-local' && object.host !== '127.0.0.1') throw invalid();
  if (object.provider_id === 'managed-llama-cpp' && typeof object.runtime_instance_id !== 'string') throw invalid();
  validateFingerprint(String(object.binding_fingerprint));
  return object as unknown as ModelBinding;
}

function validateManagedStatus(value: unknown): ManagedRuntimeStatus {
  const object = expectRecord(value);
  if (object.engine !== 'llama.cpp' || typeof object.state !== 'string') throw invalid();
  return object as unknown as ManagedRuntimeStatus;
}

function validateManagedCatalog(value: unknown): ManagedModelCatalog {
  const object = expectRecord(value);
  if (object.engine !== 'llama.cpp' || object.model_root !== '<MODEL_ROOT>' || !Array.isArray(object.models)) throw invalid();
  object.models.forEach((item) => validateModelId(String(expectRecord(item).model_id)));
  return object as unknown as ManagedModelCatalog;
}

function validateManagedStart(value: unknown): ManagedRuntimeStartResponse {
  const object = expectRecord(value);
  if (object.provider_id !== 'managed-llama-cpp' || object.state !== 'Ready') throw invalid();
  validateModelId(String(object.model_id));
  return object as unknown as ManagedRuntimeStartResponse;
}

function validateManagedLogs(value: unknown): ManagedRuntimeLogs {
  const object = expectRecord(value);
  if (!Array.isArray(object.stdout_tail) || !Array.isArray(object.stderr_tail)) throw invalid();
  return object as unknown as ManagedRuntimeLogs;
}

function validateTurnStart(value: unknown): ModelTurnStartResponse {
  const object = expectRecord(value);
  validateTurnId(String(object.turn_id));
  if (object.model_called !== false || object.tools_executed !== 0 || object.persistence !== false) throw invalid();
  return object as unknown as ModelTurnStartResponse;
}

function parseModelEvent(value: unknown): ModelGatewayEvent | null {
  const object = expectRecord(value);
  if (!isModelMethod(object.method)) return null;
  const metadata = expectRecord(object.metadata ?? {});
  return {
    method: object.method,
    sequence: Number(object.sequence),
    reply_to: String(object.reply_to),
    turn_id: validateTurnId(String(object.turn_id)),
    state: String(object.state) as ModelGatewayEvent['state'],
    text: typeof object.text === 'string' ? bounded(object.text, 65_536) : null,
    model_called: metadata.model_called === true,
    tools_executed: 0,
    persistence: false,
    generated_bytes: typeof metadata.generated_bytes === 'number' ? metadata.generated_bytes : 0,
    provider_id: metadata.provider_id === 'managed-llama-cpp' ? 'managed-llama-cpp' : 'openai-compatible-local',
    harness_id: metadata.harness_id === 'minimal' ? 'minimal' : 'native-localcomet',
    model_id: validateModelId(String(metadata.model_id ?? 'unknown-model')),
    binding_fingerprint: validateFingerprint(String(metadata.binding_fingerprint ?? '0'.repeat(64))),
    error: isRecord(metadata.error)
      ? {
          code: bounded(String(metadata.error.code ?? 'gateway_error'), 64),
          message: bounded(sanitize(String(metadata.error.message ?? 'Local model gateway error')), 240),
          retryable: metadata.error.retryable === true
        }
      : undefined
  };
}

function isModelMethod(value: unknown): value is ModelGatewayEvent['method'] {
  return typeof value === 'string' && ['model.turn.started', 'model.output.delta', 'model.turn.completed', 'model.turn.cancelled', 'model.turn.failed'].includes(value);
}

function validatePort(value: number): number {
  if (!Number.isInteger(value) || value < 1024 || value > 65535) throw invalid();
  return value;
}

function validateModelId(value: string): string {
  if (!value || value.length > 192 || /\s|\0/.test(value)) throw invalid();
  return value;
}

function validateTurnId(value: string): string {
  if (!/^[0-9a-f]{24}$/.test(value)) throw invalid();
  return value;
}

function validateFingerprint(value: string): string {
  if (!/^[0-9a-f]{64}$/.test(value)) throw invalid();
  return value;
}

function expectRecord(value: unknown): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw invalid();
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function invalid(): SanitizedGatewayError {
  return { code: 'invalid_payload', message: 'Invalid Local Model Gateway payload' };
}

function sanitize(value: string): string {
  return value.replace(/Traceback[\s\S]*/g, '<redacted>').replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>');
}

function bounded(value: string, limit: number): string {
  return value.slice(0, limit);
}
