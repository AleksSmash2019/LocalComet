import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type {
  ApprovedModelSummary,
  ApprovedRuntimeSummary,
  AssistantLocale,
  ApprovedDownloadableArtifact,
  ArtifactDownloadState,
  ArtifactInstallationStatus,
  ArtifactValidationSummary,
  CustomArtifactValidationSummary,
  CustomModelSummary,
  GatewayCatalog,
  HarnessId,
  ManagedArtifactValidationSummary,
  ManagedCatalogIdentity,
  ManagedInstalledArtifacts,
  ManagedModelCatalog,
  ManagedModelRemovalResult,
  ManagedRuntimeCatalog,
  ManagedRuntimeLogs,
  ManagedRuntimeStartResponse,
  ManagedRuntimeStatus,
  ModelReadinessSummary,
  ModelBinding,
  ModelGatewayEvent,
  ModelListResponse,
  ModelTurnCancelResponse,
  ModelTurnStartResponse,
  ProbeResponse,
  ProviderId,
  SanitizedGatewayError
} from '$lib/types/modelGateway';
import { CONTROL_PLANE_EVENT_CHANNEL } from './controlPlane';
import { requestApproval } from './approval';
import type { FileContextInclusion, FilesContextReport } from '$lib/types/files';

type InvokeArgs = Readonly<Record<string, unknown>>;

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
  isCurrent?: () => boolean;
}): Promise<ModelBinding> {
  const modelId = args.providerId === 'managed-llama-cpp' ? validateArtifactId(args.modelId) : validateModelId(args.modelId);
  const port = args.providerId === 'openai-compatible-local' ? validatePort(Number(args.port)) : null;
  const runtimeInstanceId = args.runtimeInstanceId ? args.runtimeInstanceId : null;
  const envelope = await requestApproval('model.binding.set', {
    provider_id: args.providerId,
    harness_id: args.harnessId,
    port,
    model_id: modelId,
    runtime_instance_id: runtimeInstanceId
  });
  if (args.isCurrent && !args.isCurrent()) {
    throw { code: 'stale_request', message: 'Model binding request is no longer current' };
  }
  const invokeArgs: Record<string, string | number> = {
    providerId: args.providerId,
    harnessId: args.harnessId,
    modelId,
    token: envelope.token,
    approvalId: envelope.approvalId,
    callId: envelope.callId
  };
  if (port !== null) {
    invokeArgs.port = port;
  }
  if (runtimeInstanceId !== null) {
    invokeArgs.runtimeInstanceId = runtimeInstanceId;
  }
  return validateBinding(
    await invokeExact('model_binding_set', invokeArgs)
  );
}

export async function getManagedRuntimeStatus(): Promise<ManagedRuntimeStatus> {
  return validateManagedStatus(await invokeExact('managed_runtime_status'));
}

export async function getManagedRuntimeCatalog(): Promise<ManagedRuntimeCatalog> {
  return validateManagedRuntimeCatalog(await invokeExact('managed_runtime_catalog'));
}

export async function getManagedModelCatalog(): Promise<ManagedModelCatalog> {
  return validateManagedModelCatalog(await invokeExact('managed_model_catalog'));
}

export async function getManagedInstalledArtifacts(): Promise<ManagedInstalledArtifacts> {
  return validateManagedInstalledArtifacts(await invokeExact('managed_installed_artifacts'));
}

export async function listApprovedDownloadableArtifacts(): Promise<readonly ApprovedDownloadableArtifact[]> {
  const result = await invokeExact<unknown>('list_approved_downloadable_artifacts');
  return boundedArray(result, 32).map(validateApprovedDownloadableArtifact);
}

export async function startApprovedArtifactDownload(artifactId: string): Promise<ArtifactDownloadState> {
  const requestedId = validateArtifactId(artifactId);
  const envelope = await requestApproval('artifact.download', { artifact_id: requestedId });
  const result = validateArtifactDownloadState(
    await invokeExact('start_approved_artifact_download', { artifactId: requestedId, token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId })
  );
  if (result.artifact_id !== requestedId) throw invalid();
  return result;
}

export async function startArbitraryHuggingFaceDownload(url: string): Promise<ArtifactDownloadState> {
  const customUrl = validateCanonicalHuggingFaceUrl(url);
  const envelope = await requestApproval('artifact.download', { custom_url: customUrl });
  return validateArtifactDownloadState(
    await invokeExact('start_approved_artifact_download', {
      customUrl,
      token: envelope.token,
      approvalId: envelope.approvalId,
      callId: envelope.callId
    })
  );
}

export interface HfModelSummary {
  readonly id: string;
  readonly downloads: number;
  readonly tags: readonly string[];
  readonly last_modified: string;
  readonly pipeline_tag: string | null;
}

export interface HfRepoFile {
  readonly filename: string;
  readonly size: number | null;
}

/**
 * Search Hugging Face through the Rust backend.
 *
 * The webview must not call huggingface.co directly: routing through Tauri
 * keeps every outbound request behind the vetted host allowlist and the
 * no-redirect/no-proxy policy enforced in src-tauri/src/hf_catalog.rs.
 */
export async function searchHuggingFaceModels(query: string): Promise<readonly HfModelSummary[]> {
  const result = await invokeExact<unknown>('hf_search_models', { query });
  return boundedArray(result, 30).map((item) => {
    const object = expectRecord(item);
    return {
      id: String(object.id ?? ''),
      downloads: Number(object.downloads ?? 0),
      tags: boundedArray(object.tags, 24).map((tag) => String(tag)),
      last_modified: String(object.last_modified ?? ''),
      pipeline_tag: object.pipeline_tag == null ? null : String(object.pipeline_tag)
    };
  });
}

/** List downloadable GGUF files for one repository, via the Rust backend. */
export async function listHuggingFaceRepoFiles(modelId: string): Promise<readonly HfRepoFile[]> {
  const result = await invokeExact<unknown>('hf_list_repo_files', { modelId });
  return boundedArray(result, 64).map((item) => {
    const object = expectRecord(item);
    return {
      filename: String(object.filename ?? ''),
      size: object.size == null ? null : Number(object.size)
    };
  });
}

export async function getArtifactDownloadState(jobId: string): Promise<ArtifactDownloadState> {
  return validateArtifactDownloadState(
    await invokeExact('get_artifact_download_state', { jobId: validateDownloadJobId(jobId) })
  );
}

export async function cancelArtifactDownload(jobId: string): Promise<ArtifactDownloadState> {
  return validateArtifactDownloadState(
    await invokeExact('cancel_artifact_download', { jobId: validateDownloadJobId(jobId) })
  );
}

export async function removeManagedModel(modelId: string): Promise<ManagedModelRemovalResult> {
  const requestedId = validateArtifactId(modelId);
  const envelope = await requestApproval('artifact.remove', { model_id: requestedId });
  const object = expectExactRecord(
    await invokeExact('remove_managed_model', { modelId: requestedId, token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId }),
    ['model_id', 'removed']
  );
  if (object.model_id !== requestedId || object.removed !== true) throw invalid();
  return { model_id: requestedId, removed: true };
}

export async function getManagedArtifactValidationStatus(artifactId: string): Promise<ManagedArtifactValidationSummary> {
  const requestedId = validateArtifactId(artifactId);
  const result = validateManagedArtifactValidationSummary(
    await invokeExact('managed_artifact_validation_status', { artifactId: requestedId })
  );
  if (result.artifact_id !== requestedId) throw invalid();
  return result;
}

export async function getManagedModelReadiness(modelId: string): Promise<ModelReadinessSummary> {
  const requestedId = validateArtifactId(modelId);
  const result = validateModelReadiness(
    await invokeExact('managed_model_readiness', { modelId: requestedId })
  );
  if (result.model_id !== requestedId) throw invalid();
  return result;
}

export async function startManagedRuntime(
  modelId: string,
  customSha256OrIsCurrent?: string | (() => boolean),
  maybeIsCurrent?: () => boolean
): Promise<ManagedRuntimeStartResponse> {
  const requestedId = validateArtifactId(modelId);
  const customSha256 = typeof customSha256OrIsCurrent === 'string'
    ? validateHash(customSha256OrIsCurrent)
    : null;
  const isCurrent = typeof customSha256OrIsCurrent === 'function'
    ? customSha256OrIsCurrent
    : maybeIsCurrent;
  const approvalInput = customSha256 === null
    ? { model_id: requestedId }
    : { model_id: requestedId, custom_sha256: customSha256 };
  const envelope = await requestApproval('runtime.start', approvalInput);
  if (isCurrent && !isCurrent()) {
    throw { code: 'stale_request', message: 'Managed runtime start request is no longer current' };
  }
  const invokeArgs: Record<string, string> = {
    modelId: requestedId,
    token: envelope.token,
    approvalId: envelope.approvalId,
    callId: envelope.callId
  };
  if (customSha256 !== null) invokeArgs.customSha256 = customSha256;
  return validateManagedStart(await invokeExact('managed_runtime_start', invokeArgs));
}

export async function stopManagedRuntime(): Promise<void> {
  const envelope = await requestApproval('runtime.stop', {});
  await invokeExact('managed_runtime_stop', { token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId });
}

export async function getManagedRuntimeLogs(): Promise<ManagedRuntimeLogs> {
  return validateManagedLogs(await invokeExact('managed_runtime_logs'));
}

export async function startModelTurn(args: {
  requestId: string;
  chatSessionId: string;
  modelId: string;
  submittedAtUnixMs: number;
  maxTokens: number;
  prompt: string;
  fileIds?: readonly string[];
  locale: AssistantLocale;
  bindingFingerprint: string;
  agentPermissions: { files: boolean; shell: boolean; computerUse: boolean; tools: boolean };
  messages?: readonly unknown[];
}): Promise<ModelTurnStartResponse> {
  const requestId = validateTurnId(args.requestId);
  const chatSessionId = validateChatSessionId(args.chatSessionId);
  const modelId = validateArtifactId(args.modelId);
  const submittedAtUnixMs = positiveSafeInteger(args.submittedAtUnixMs);
  const maxTokens = validateMaxTokens(args.maxTokens);
  const fileIds = validateFileIds(args.fileIds ?? []);
  const result = validateTurnStart(
    await invokeExact('model_turn_start', {
      requestId,
      chatSessionId,
      modelId,
      submittedAtUnixMs,
      maxTokens,
      prompt: bounded(args.prompt, 16_384),
      fileIds,
      locale: validateLocale(args.locale),
      bindingFingerprint: validateFingerprint(args.bindingFingerprint),
      agentPermissions: args.agentPermissions,
      messages: args.messages ? JSON.parse(JSON.stringify(args.messages)) : []
    })
  );
  if (
    result.request_id !== requestId ||
    result.turn_id !== requestId ||
    result.chat_session_id !== chatSessionId ||
    result.model_id !== modelId ||
    result.submitted_at_unix_ms !== submittedAtUnixMs ||
    result.max_tokens !== maxTokens ||
    result.binding_fingerprint !== args.bindingFingerprint
  ) throw invalid();
  return result;
}

function validateFileIds(value: readonly string[]): readonly string[] {
  if (!Array.isArray(value) || value.length > 32) throw invalid();
  const unique = new Set<string>();
  for (const fileId of value) {
    if (typeof fileId !== 'string' || !/^[0-9a-f]{64}$/.test(fileId) || unique.has(fileId)) {
      throw invalid();
    }
    unique.add(fileId);
  }
  return [...unique];
}

function validateLocale(value: unknown): AssistantLocale {
  if (value !== 'ru' && value !== 'en') throw invalid();
  return value;
}

export async function cancelModelTurn(requestId: string): Promise<ModelTurnCancelResponse> {
  const expectedRequestId = validateTurnId(requestId);
  const result = validateTurnCancel(
    await invokeExact('model_turn_cancel', { requestId: expectedRequestId })
  );
  if (result.request_id !== expectedRequestId || result.turn_id !== expectedRequestId) throw invalid();
  return result;
}

export async function subscribeModelGatewayEvents(
  callback: (event: ModelGatewayEvent) => void,
  onProtocolError?: (error: SanitizedGatewayError) => void,
  options: { readonly toolsEnabled?: boolean } = {}
): Promise<() => void> {
  const toolsEnabled = options.toolsEnabled === true;
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    try {
      const parsed = parseModelEvent(event.payload, toolsEnabled);
      if (parsed) callback(parsed);
    } catch (error) {
      onProtocolError?.(normalizeGatewayError(error));
    }
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
  const object = expectExactRecord(value, [
    'engine',
    'state',
    'installation',
    'runtime_version',
    'runtime_instance_id',
    'runtime_instance_fingerprint',
    'model_id',
    'model_display_name',
    'binding_fingerprint',
    'model_state',
    'inference_ready',
    'last_error'
  ]);
  if (object.engine !== 'llama.cpp') throw invalid();
  return {
    engine: 'llama.cpp',
    state: exactString(object.state, ['NotInstalled', 'Stopped', 'Validating', 'Starting', 'Ready', 'Stopping', 'Failed']),
    installation: exactString(object.installation, ['Installed', 'Not installed']),
    runtime_version: nullableSafeText(object.runtime_version, 96),
    runtime_instance_id: nullablePattern(object.runtime_instance_id, /^[0-9a-f]{32}$/),
    runtime_instance_fingerprint: nullableHash(object.runtime_instance_fingerprint),
    model_id: object.model_id === null ? null : validateArtifactId(String(object.model_id)),
    model_display_name: nullableSafeText(object.model_display_name, 192),
    binding_fingerprint: nullableHash(object.binding_fingerprint),
    model_state: exactString(object.model_state, ['Unavailable', 'Validating', 'Loading', 'Ready', 'Failed', 'Unloading']),
    inference_ready: exactBoolean(object.inference_ready),
    last_error: nullableSafeText(object.last_error, 240)
  };
}

function validateManagedRuntimeCatalog(value: unknown): ManagedRuntimeCatalog {
  const object = expectExactRecord(value, ['schema_version', 'catalog_id', 'catalog_version', 'catalog_digest', 'runtimes']);
  const identity = validateCatalogIdentity(object);
  const runtimes = boundedArray(object.runtimes, 32).map(validateApprovedRuntime);
  validateUniqueSorted(runtimes.map((runtime) => runtime.runtime_id));
  return { ...identity, runtimes };
}

function validateManagedModelCatalog(value: unknown): ManagedModelCatalog {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'engine',
    'model_root',
    'models',
    'maximum_models',
    'custom_models',
    'maximum_custom_models'
  ]);
  if (
    object.engine !== 'llama.cpp' ||
    object.model_root !== '<MANAGED_MODEL_ROOT>' ||
    object.maximum_models !== 32 ||
    object.maximum_custom_models !== 32
  ) throw invalid();
  const identity = validateCatalogIdentity(object);
  const models = boundedArray(object.models, 32).map(validateApprovedModel);
  const customModels = boundedArray(object.custom_models, 32).map(validateCustomModel);
  validateUniqueSorted(models.map((model) => model.model_id));
  validateUniqueSorted(customModels.map((model) => model.model_id));
  validateUnique([...models, ...customModels].map((model) => model.model_id));
  return {
    ...identity,
    engine: 'llama.cpp',
    model_root: '<MANAGED_MODEL_ROOT>',
    models,
    maximum_models: 32,
    custom_models: customModels,
    maximum_custom_models: 32
  };
}

function validateManagedInstalledArtifacts(value: unknown): ManagedInstalledArtifacts {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'artifacts',
    'custom_artifacts'
  ]);
  const identity = validateCatalogIdentity(object);
  const artifacts = boundedArray(object.artifacts, 64).map(validateArtifactValidationSummary);
  const customArtifacts = boundedArray(object.custom_artifacts, 32).map(validateCustomArtifactValidationSummary);
  validateUnique(artifacts.map((artifact) => artifact.artifact_id));
  validateUnique(customArtifacts.map((artifact) => artifact.artifact_id));
  validateUnique([...artifacts, ...customArtifacts].map((artifact) => artifact.artifact_id));
  return { ...identity, artifacts, custom_artifacts: customArtifacts };
}

function validateApprovedDownloadableArtifact(value: unknown): ApprovedDownloadableArtifact {
  const object = expectExactRecord(value, [
    'artifact_id',
    'kind',
    'trust_kind',
    'display_name',
    'source_identity',
    'expected_bytes',
    'license_id',
    'format',
    'quantization',
    'user_confirmation_required',
    'automatic_download'
  ]);
  const kind = exactString(object.kind, ['runtime', 'model']);
  const format = object.format === null ? null : safeText(object.format, 64);
  const quantization = object.quantization === null ? null : safeText(object.quantization, 64);
  if (
    object.trust_kind !== 'approved_catalog' ||
    object.user_confirmation_required !== true ||
    object.automatic_download !== false ||
    (kind === 'runtime' && (format !== 'zip' || quantization !== null)) ||
    (kind === 'model' && (format !== 'GGUF' || quantization !== 'Q4_K_M'))
  ) throw invalid();
  return {
    artifact_id: validateArtifactId(String(object.artifact_id)),
    kind,
    trust_kind: 'approved_catalog',
    display_name: safeText(object.display_name, 192),
    source_identity: safeText(object.source_identity, 256),
    expected_bytes: positiveSafeInteger(object.expected_bytes),
    license_id: safeText(object.license_id, 128),
    format,
    quantization,
    user_confirmation_required: true,
    automatic_download: false
  };
}

function validateArtifactDownloadState(value: unknown): ArtifactDownloadState {
  const object = expectExactRecord(value, [
    'job_id',
    'artifact_id',
    'lifecycle',
    'expected_bytes',
    'received_bytes',
    'percent',
    'started_utc_ms',
    'updated_utc_ms',
    'error_code'
  ]);
  const expectedBytes = positiveSafeInteger(object.expected_bytes);
  const receivedBytes = nonNegativeSafeInteger(object.received_bytes);
  const lifecycle = exactString(object.lifecycle, [
    'idle',
    'awaiting_confirmation',
    'checking_disk',
    'downloading',
    'cancelling',
    'cancelled',
    'verifying_size',
    'verifying_hash',
    'validating_artifact',
    'installing',
    'completed',
    'failed'
  ]);
  const percent = object.percent === null ? null : nonNegativeSafeInteger(object.percent);
  const errorCode = object.error_code === null ? null : safeText(object.error_code, 64);
  const startedUtcMs = nonNegativeSafeInteger(object.started_utc_ms);
  const updatedUtcMs = nonNegativeSafeInteger(object.updated_utc_ms);
  if (
    receivedBytes > expectedBytes ||
    updatedUtcMs < startedUtcMs ||
    (percent !== null && (percent > 100 || percent !== Math.floor((receivedBytes * 100) / expectedBytes))) ||
    (lifecycle === 'completed' && (receivedBytes !== expectedBytes || percent !== 100 || errorCode !== null)) ||
    (lifecycle === 'failed' && errorCode === null) ||
    (lifecycle !== 'failed' && errorCode !== null)
  ) throw invalid();
  return {
    job_id: validateDownloadJobId(String(object.job_id)),
    artifact_id: validateArtifactId(String(object.artifact_id)),
    lifecycle,
    expected_bytes: expectedBytes,
    received_bytes: receivedBytes,
    percent,
    started_utc_ms: startedUtcMs,
    updated_utc_ms: updatedUtcMs,
    error_code: errorCode
  };
}

function validateManagedArtifactValidationSummary(value: unknown): ManagedArtifactValidationSummary {
  const object = expectRecord(value);
  return object.trust_kind === 'user_supplied'
    ? validateCustomArtifactValidationSummary(value)
    : validateArtifactValidationSummary(value);
}

function validateArtifactValidationSummary(value: unknown): ArtifactValidationSummary {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'artifact_id',
    'kind',
    'catalog_status',
    'installation_status',
    'expected_bytes',
    'expected_sha256',
    'observed_bytes',
    'observed_sha256',
    'validation_code',
    'verified_unix_ms'
  ]);
  const identity = validateCatalogIdentity(object);
  const kind = exactString(object.kind, ['runtime', 'model']);
  const installationStatus = validateInstallationStatus(object.installation_status);
  const expectedBytes = positiveSafeInteger(object.expected_bytes);
  const expectedSha256 = validateHash(object.expected_sha256);
  const observedBytes = object.observed_bytes === null ? null : nonNegativeSafeInteger(object.observed_bytes);
  const observedSha256 = object.observed_sha256 === null ? null : validateHash(object.observed_sha256);
  const validationCode = safeText(object.validation_code, 64);
  if (validationCode !== installationStatus) throw invalid();
  if (installationStatus === 'not_installed' && (observedBytes !== null || observedSha256 !== null)) throw invalid();
  if (
    installationStatus === 'valid' &&
    ((kind === 'model' && (observedBytes !== expectedBytes || observedSha256 !== expectedSha256)) ||
      (kind === 'runtime' && (observedBytes !== null || observedSha256 !== null)))
  ) throw invalid();
  return {
    ...identity,
    artifact_id: validateArtifactId(String(object.artifact_id)),
    kind,
    catalog_status: validateCatalogStatus(object.catalog_status),
    installation_status: installationStatus,
    expected_bytes: expectedBytes,
    expected_sha256: expectedSha256,
    observed_bytes: observedBytes,
    observed_sha256: observedSha256,
    validation_code: validationCode,
    verified_unix_ms: nonNegativeSafeInteger(object.verified_unix_ms)
  };
}

function validateCustomArtifactValidationSummary(value: unknown): CustomArtifactValidationSummary {
  const object = expectExactRecord(value, [
    'artifact_id',
    'kind',
    'trust_kind',
    'installation_status',
    'expected_bytes',
    'expected_sha256',
    'observed_bytes',
    'observed_sha256',
    'validation_code',
    'verified_unix_ms'
  ]);
  if (object.kind !== 'model' || object.trust_kind !== 'user_supplied') throw invalid();
  const installationStatus = validateInstallationStatus(object.installation_status);
  const expectedBytes = positiveSafeInteger(object.expected_bytes);
  const expectedSha256 = validateHash(object.expected_sha256);
  const observedBytes = object.observed_bytes === null ? null : nonNegativeSafeInteger(object.observed_bytes);
  const observedSha256 = object.observed_sha256 === null ? null : validateHash(object.observed_sha256);
  const validationCode = safeText(object.validation_code, 64);
  if (validationCode !== installationStatus) throw invalid();
  if (installationStatus === 'not_installed' && (observedBytes !== null || observedSha256 !== null)) throw invalid();
  if (installationStatus === 'valid' && (observedBytes !== expectedBytes || observedSha256 !== expectedSha256)) throw invalid();
  return {
    artifact_id: validateArtifactId(String(object.artifact_id)),
    kind: 'model',
    trust_kind: 'user_supplied',
    installation_status: installationStatus,
    expected_bytes: expectedBytes,
    expected_sha256: expectedSha256,
    observed_bytes: observedBytes,
    observed_sha256: observedSha256,
    validation_code: validationCode,
    verified_unix_ms: nonNegativeSafeInteger(object.verified_unix_ms)
  };
}

function validateModelReadiness(value: unknown): ModelReadinessSummary {
  const object = expectExactRecord(value, [
    'schema_version',
    'catalog_id',
    'catalog_version',
    'catalog_digest',
    'model_id',
    'model_trust_kind',
    'model_status',
    'compatible_runtime_ids',
    'selected_runtime_id',
    'runtime_status',
    'compatibility',
    'readiness',
    'launchable'
  ]);
  const identity = validateCatalogIdentity(object);
  const compatibleRuntimeIds = boundedArray(object.compatible_runtime_ids, 32).map((item) => validateArtifactId(String(item)));
  validateUniqueSorted(compatibleRuntimeIds);
  const selectedRuntimeId = object.selected_runtime_id === null ? null : validateArtifactId(String(object.selected_runtime_id));
  const modelStatus = validateInstallationStatus(object.model_status);
  const runtimeStatus = object.runtime_status === null ? null : validateInstallationStatus(object.runtime_status);
  const compatibility = exactString(object.compatibility, [
    'compatible',
    'no_compatible_runtime_installed',
    'incompatible_runtime_installed'
  ]);
  const readiness = exactString(object.readiness, [
    'ready',
    'model_not_installed',
    'model_invalid',
    'runtime_not_installed',
    'runtime_invalid',
    'incompatible'
  ]);
  if (typeof object.launchable !== 'boolean') throw invalid();
  const launchable = object.launchable;
  const truthfullyLaunchable =
    modelStatus === 'valid' &&
    runtimeStatus === 'valid' &&
    compatibility === 'compatible' &&
    readiness === 'ready' &&
    selectedRuntimeId !== null &&
    compatibleRuntimeIds.includes(selectedRuntimeId);
  if (launchable !== truthfullyLaunchable) throw invalid();
  if (compatibility === 'compatible' && (runtimeStatus !== 'valid' || selectedRuntimeId === null || !compatibleRuntimeIds.includes(selectedRuntimeId))) throw invalid();
  if (compatibility === 'no_compatible_runtime_installed' && selectedRuntimeId !== null) throw invalid();
  if (readiness === 'model_not_installed' && modelStatus !== 'not_installed') throw invalid();
  if (readiness === 'model_invalid' && ['valid', 'not_installed'].includes(modelStatus)) throw invalid();
  if (readiness === 'runtime_not_installed' && (modelStatus !== 'valid' || runtimeStatus !== 'not_installed')) throw invalid();
  if (readiness === 'runtime_invalid' && (modelStatus !== 'valid' || runtimeStatus === null || ['valid', 'not_installed'].includes(runtimeStatus))) throw invalid();
  if (readiness === 'incompatible' && compatibility !== 'incompatible_runtime_installed') throw invalid();
  return {
    ...identity,
    model_id: validateArtifactId(String(object.model_id)),
    model_trust_kind: exactString(object.model_trust_kind, ['approved_catalog', 'user_supplied']),
    model_status: modelStatus,
    compatible_runtime_ids: compatibleRuntimeIds,
    selected_runtime_id: selectedRuntimeId,
    runtime_status: runtimeStatus,
    compatibility,
    readiness,
    launchable
  };
}

function validateManagedStart(value: unknown): ManagedRuntimeStartResponse {
  const object = expectExactRecord(value, [
    'state',
    'model_state',
    'inference_ready',
    'provider_id',
    'model_id',
    'model_display_name',
    'runtime_instance_id',
    'runtime_instance_fingerprint'
  ]);
  if (object.provider_id !== 'managed-llama-cpp' || object.state !== 'Ready' || object.model_state !== 'Ready' || object.inference_ready !== true) throw invalid();
  return {
    state: 'Ready',
    model_state: 'Ready',
    inference_ready: true,
    provider_id: 'managed-llama-cpp',
    model_id: validateArtifactId(String(object.model_id)),
    model_display_name: safeText(object.model_display_name, 192),
    runtime_instance_id: patternString(object.runtime_instance_id, /^[0-9a-f]{32}$/),
    runtime_instance_fingerprint: validateHash(object.runtime_instance_fingerprint)
  };
}

function validateManagedLogs(value: unknown): ManagedRuntimeLogs {
  const object = expectExactRecord(value, ['stdout_tail', 'stderr_tail']);
  return {
    stdout_tail: boundedArray(object.stdout_tail, 200).map((line) => safeTextAllowEmpty(line, 2_048)),
    stderr_tail: boundedArray(object.stderr_tail, 200).map((line) => safeTextAllowEmpty(line, 2_048))
  };
}

function validateTurnStart(value: unknown): ModelTurnStartResponse {
  const object = expectRecord(value);
  const requestId = validateTurnId(String(object.request_id));
  const turnId = validateTurnId(String(object.turn_id));
  if (turnId !== requestId || object.state !== 'Accepted') throw invalid();
  const response: ModelTurnStartResponse = {
    request_id: requestId,
    chat_session_id: validateChatSessionId(object.chat_session_id),
    turn_id: turnId,
    state: 'Accepted',
    model_id: validateArtifactId(String(object.model_id)),
    submitted_at_unix_ms: positiveSafeInteger(object.submitted_at_unix_ms),
    max_tokens: validateMaxTokens(object.max_tokens),
    binding_fingerprint: validateFingerprint(String(object.binding_fingerprint))
  };
  return object.file_context === undefined
    ? response
    : { ...response, file_context: validateFilesContextReport(object.file_context) };
}

function validateFilesContextReport(value: unknown): FilesContextReport {
  const object = expectExactRecord(value, [
    'source_bytes',
    'source_characters',
    'included_bytes',
    'included_characters',
    'truncated',
    'files'
  ]);
  const sourceBytes = boundedNonNegativeInteger(object.source_bytes, 5 * 1024 * 1024);
  const sourceCharacters = boundedNonNegativeInteger(object.source_characters, 5 * 1024 * 1024);
  const includedBytes = boundedNonNegativeInteger(object.included_bytes, sourceBytes);
  const includedCharacters = boundedNonNegativeInteger(object.included_characters, sourceCharacters);
  const files = boundedArray(object.files, 32).map(validateFileContextInclusion);
  const ids = files.map((file) => file.file_id);
  validateUnique(ids);
  if (
    files.length === 0 ||
    object.truncated !== (includedBytes !== sourceBytes) ||
    files.reduce((total, file) => total + file.original_bytes, 0) !== sourceBytes ||
    files.reduce((total, file) => total + file.original_characters, 0) !== sourceCharacters ||
    files.reduce((total, file) => total + file.included_bytes, 0) !== includedBytes ||
    files.reduce((total, file) => total + file.included_characters, 0) !== includedCharacters
  ) throw invalid();
  return {
    source_bytes: sourceBytes,
    source_characters: sourceCharacters,
    included_bytes: includedBytes,
    included_characters: includedCharacters,
    truncated: object.truncated as boolean,
    files
  };
}

function validateFileContextInclusion(value: unknown): FileContextInclusion {
  const object = expectExactRecord(value, [
    'file_id',
    'filename',
    'original_bytes',
    'original_characters',
    'included_bytes',
    'included_characters',
    'inclusion'
  ]);
  const originalBytes = boundedNonNegativeInteger(object.original_bytes, 2 * 1024 * 1024);
  const originalCharacters = boundedNonNegativeInteger(object.original_characters, 2 * 1024 * 1024);
  const includedBytes = boundedNonNegativeInteger(object.included_bytes, originalBytes);
  const includedCharacters = boundedNonNegativeInteger(object.included_characters, originalCharacters);
  const inclusion = exactString(object.inclusion, ['full', 'bounded_excerpt']);
  if (
    (inclusion === 'full' && (includedBytes !== originalBytes || includedCharacters !== originalCharacters)) ||
    (inclusion === 'bounded_excerpt' && (includedBytes >= originalBytes || includedCharacters >= originalCharacters))
  ) throw invalid();
  return {
    file_id: patternString(object.file_id, /^[0-9a-f]{64}$/),
    filename: validateContextFilename(object.filename),
    original_bytes: originalBytes,
    original_characters: originalCharacters,
    included_bytes: includedBytes,
    included_characters: includedCharacters,
    inclusion
  };
}

function validateContextFilename(value: unknown): string {
  const filename = safeText(value, 255);
  if (/[\\/:]/.test(filename) || filename === '.' || filename === '..') throw invalid();
  return filename;
}

function validateTurnCancel(value: unknown): ModelTurnCancelResponse {
  const object = expectExactRecord(value, [
    'request_id',
    'turn_id',
    'state',
    'accepted',
    'already_terminal',
    'worker_alive'
  ]);
  const requestId = validateTurnId(String(object.request_id));
  const turnId = validateTurnId(String(object.turn_id));
  if (requestId !== turnId || typeof object.accepted !== 'boolean' || typeof object.already_terminal !== 'boolean' || typeof object.worker_alive !== 'boolean') {
    throw invalid();
  }
  const state = exactString(object.state, ['Cancelling', 'Cancelled']);
  const acceptedActive = object.accepted === true && object.already_terminal === false && (
    (state === 'Cancelling' && object.worker_alive === true) ||
    (state === 'Cancelled' && object.worker_alive === false)
  );
  const alreadyTerminal = object.accepted === false && object.already_terminal === true && object.worker_alive === false && state === 'Cancelled';
  if (!acceptedActive && !alreadyTerminal) throw invalid();
  return {
    request_id: requestId,
    turn_id: turnId,
    state,
    accepted: object.accepted,
    already_terminal: object.already_terminal,
    worker_alive: object.worker_alive
  };
}

function parseModelEvent(value: unknown, toolsEnabled: boolean): ModelGatewayEvent | null {
  const object = expectRecord(value);
  if (!isModelMethod(object.method)) return null;
  const metadata = expectRecord(object.metadata ?? {});
  const requestId = validateTurnId(String(object.request_id));
  const turnId = validateTurnId(String(object.turn_id));
  const replyTo = validateTurnId(String(object.reply_to));
  if (requestId !== turnId || requestId !== replyTo) throw invalid();
  const state = exactString(object.state, ['Streaming', 'Completed', 'Cancelled', 'TimedOut', 'Failed', 'ToolCalls']);
  const expectedState: Readonly<Record<ModelGatewayEvent['method'], ModelGatewayEvent['state']>> = {
    'model.turn.started': 'Streaming',
    'model.output.delta': 'Streaming',
    'model.turn.completed': 'Completed',
    'model.turn.cancelled': 'Cancelled',
    'model.turn.timed_out': 'TimedOut',
    'model.turn.failed': 'Failed',
    'model.tool.request': 'Streaming',
    'model.turn.tool_calls': 'ToolCalls'
  };
  if (state !== expectedState[object.method]) throw invalid();
  const toolsExecuted = nonNegativeSafeInteger(metadata.tools_executed);
  const persistence = exactBoolean(metadata.persistence);
  if (persistence !== false) throw invalid();
  const isToolEvent = object.method === 'model.tool.request' || object.method === 'model.turn.tool_calls';
  if ((isToolEvent && !toolsEnabled) || (!isToolEvent && toolsExecuted !== 0)) throw invalid();
  const toolCalls = isToolEvent ? validateModelToolCalls(metadata.tool_calls, object.method === 'model.tool.request') : undefined;
  if (isToolEvent && toolsExecuted !== toolCalls?.length && object.method === 'model.turn.tool_calls') throw invalid();
  return {
    method: object.method,
    sequence: nonNegativeSafeInteger(object.sequence),
    reply_to: replyTo,
    request_id: requestId,
    chat_session_id: validateChatSessionId(object.chat_session_id),
    turn_id: turnId,
    state,
    text: typeof object.text === 'string' ? bounded(object.text, 65_536) : null,
    model_called: exactBoolean(metadata.model_called),
    tools_executed: toolsExecuted,
    ...(toolCalls ? { tool_calls: toolCalls } : {}),
    persistence: false,
    generated_bytes: nonNegativeSafeInteger(metadata.generated_bytes),
    provider_id: exactString(metadata.provider_id, ['managed-llama-cpp', 'openai-compatible-local']),
    harness_id: exactString(metadata.harness_id, ['minimal', 'native-localcomet']),
    model_id: validateArtifactId(String(object.model_id)),
    binding_fingerprint: validateFingerprint(String(metadata.binding_fingerprint)),
    error: isRecord(metadata.error)
      ? {
          code: bounded(String(metadata.error.code ?? 'gateway_error'), 64),
          message: bounded(sanitize(String(metadata.error.message ?? 'Local model gateway error')), 240),
          retryable: metadata.error.retryable === true
        }
      : undefined
  };
}

function validateModelToolCalls(value: unknown, single: boolean) {
  if (!Array.isArray(value) || value.length === 0 || (single && value.length !== 1)) throw invalid();
  return value.map((item) => {
    const call = expectExactRecord(item, ['id', 'name', 'arguments']);
    if (typeof call.id !== 'string' || typeof call.name !== 'string') throw invalid();
    const id = bounded(call.id, 256);
    const name = bounded(call.name, 256);
    const args = expectRecord(call.arguments);
    if (!id.trim() || !name.trim()) throw invalid();
    return { id, name, arguments: args };
  });
}

function isModelMethod(value: unknown): value is ModelGatewayEvent['method'] {
  return typeof value === 'string' && ['model.turn.started', 'model.output.delta', 'model.turn.completed', 'model.turn.cancelled', 'model.turn.timed_out', 'model.turn.failed', 'model.tool.request', 'model.turn.tool_calls'].includes(value);
}

function validateApprovedRuntime(value: unknown): ApprovedRuntimeSummary {
  const object = expectExactRecord(value, [
    'runtime_id',
    'provider',
    'release_tag',
    'platform',
    'architecture',
    'variant',
    'upstream_repository',
    'upstream_revision',
    'asset_filename',
    'asset_bytes',
    'asset_sha256',
    'archive_format',
    'permitted_bind_scope',
    'supported_api_protocol',
    'license_id',
    'public_distribution',
    'status'
  ]);
  if (
    object.platform !== 'windows' ||
    object.architecture !== 'x86-64' ||
    object.variant !== 'cpu' ||
    object.archive_format !== 'zip' ||
    object.permitted_bind_scope !== 'loopback-only' ||
    object.supported_api_protocol !== 'openai-compatible-v1' ||
    object.public_distribution !== false
  ) throw invalid();
  return {
    runtime_id: validateArtifactId(String(object.runtime_id)),
    provider: safeText(object.provider, 256),
    release_tag: safeText(object.release_tag, 256),
    platform: 'windows',
    architecture: 'x86-64',
    variant: 'cpu',
    upstream_repository: safeText(object.upstream_repository, 256),
    upstream_revision: safeText(object.upstream_revision, 256),
    asset_filename: safeFilename(object.asset_filename),
    asset_bytes: positiveSafeInteger(object.asset_bytes),
    asset_sha256: validateHash(object.asset_sha256),
    archive_format: 'zip',
    permitted_bind_scope: 'loopback-only',
    supported_api_protocol: 'openai-compatible-v1',
    license_id: safeText(object.license_id, 256),
    public_distribution: false,
    status: validateCatalogStatus(object.status)
  };
}

function validateApprovedModel(value: unknown): ApprovedModelSummary {
  const object = expectExactRecord(value, [
    'model_id',
    'provider',
    'family',
    'display_name',
    'format',
    'quantization',
    'upstream_repository',
    'upstream_revision',
    'asset_filename',
    'asset_bytes',
    'asset_sha256',
    'license_id',
    'compatible_runtime_ids',
    'public_distribution',
    'installer_bundled',
    'bootstrap_purpose',
    'status'
  ]);
  if (
    object.format !== 'GGUF' ||
    object.quantization !== 'Q4_K_M' ||
    object.public_distribution !== false ||
    object.installer_bundled !== false ||
    object.bootstrap_purpose !== 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION'
  ) throw invalid();
  const compatibleRuntimeIds = boundedArray(object.compatible_runtime_ids, 32).map((item) => validateArtifactId(String(item)));
  validateUniqueSorted(compatibleRuntimeIds);
  return {
    model_id: validateArtifactId(String(object.model_id)),
    provider: safeText(object.provider, 256),
    family: safeText(object.family, 256),
    display_name: safeText(object.display_name, 256),
    format: 'GGUF',
    quantization: 'Q4_K_M',
    upstream_repository: safeText(object.upstream_repository, 256),
    upstream_revision: safeText(object.upstream_revision, 256),
    asset_filename: safeFilename(object.asset_filename),
    asset_bytes: positiveSafeInteger(object.asset_bytes),
    asset_sha256: validateHash(object.asset_sha256),
    license_id: safeText(object.license_id, 256),
    compatible_runtime_ids: compatibleRuntimeIds,
    public_distribution: false,
    installer_bundled: false,
    bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION',
    status: validateCatalogStatus(object.status)
  };
}

function validateCustomModel(value: unknown): CustomModelSummary {
  const object = expectExactRecord(value, [
    'model_id',
    'display_name',
    'format',
    'source_url',
    'source_repository',
    'source_revision',
    'asset_filename',
    'asset_bytes',
    'asset_sha256',
    'license_id',
    'compatible_runtime_ids',
    'trust_kind'
  ]);
  if (object.format !== 'GGUF' || object.license_id !== null || object.trust_kind !== 'user_supplied') throw invalid();
  const sourceUrl = validateCanonicalHuggingFaceUrl(object.source_url);
  const assetFilename = safeFilename(object.asset_filename);
  const urlFilename = new URL(sourceUrl).pathname.split('/').at(-1);
  if (!assetFilename.endsWith('.gguf') || urlFilename !== assetFilename) throw invalid();
  const compatibleRuntimeIds = boundedArray(object.compatible_runtime_ids, 32).map((item) => validateArtifactId(String(item)));
  validateUniqueSorted(compatibleRuntimeIds);
  return {
    model_id: validateArtifactId(String(object.model_id)),
    display_name: safeText(object.display_name, 256),
    format: 'GGUF',
    source_url: sourceUrl,
    source_repository: safeText(object.source_repository, 256),
    source_revision: safeText(object.source_revision, 256),
    asset_filename: assetFilename,
    asset_bytes: positiveSafeInteger(object.asset_bytes),
    asset_sha256: validateHash(object.asset_sha256),
    license_id: null,
    compatible_runtime_ids: compatibleRuntimeIds,
    trust_kind: 'user_supplied'
  };
}

function validateCatalogIdentity(object: Readonly<Record<string, unknown>>): ManagedCatalogIdentity {
  if (object.schema_version !== 1 || object.catalog_id !== 'localcomet-approved-artifacts') throw invalid();
  return {
    schema_version: 1,
    catalog_id: 'localcomet-approved-artifacts',
    catalog_version: patternString(object.catalog_version, /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/),
    catalog_digest: validateHash(object.catalog_digest)
  };
}

function validateCatalogStatus(value: unknown): 'approved_internal_bootstrap' {
  return exactString(value, ['approved_internal_bootstrap']);
}

function validateInstallationStatus(value: unknown): ArtifactInstallationStatus {
  return exactString(value, [
    'not_installed',
    'valid',
    'bytes_mismatch',
    'hash_mismatch',
    'invalid_path',
    'invalid_format',
    'missing_required_file',
    'unexpected_file',
    'io_error'
  ]);
}

function validateArtifactId(value: string): string {
  if (!/^[a-z0-9][a-z0-9._-]{2,95}$/.test(value)) throw invalid();
  return value;
}

function validateDownloadJobId(value: string): string {
  if (!/^[0-9a-f]{64}$/.test(value)) throw invalid();
  return value;
}

function validateHash(value: unknown): string {
  return patternString(value, /^[0-9a-f]{64}$/);
}

function validateCanonicalHuggingFaceUrl(value: unknown): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > 2_048) throw invalid();
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw invalid();
  }
  const segments = parsed.pathname.split('/');
  if (
    parsed.href !== value ||
    parsed.protocol !== 'https:' ||
    parsed.hostname !== 'huggingface.co' ||
    parsed.host !== 'huggingface.co' ||
    parsed.port !== '' ||
    parsed.username !== '' ||
    parsed.password !== '' ||
    parsed.search !== '' ||
    parsed.hash !== '' ||
    segments.length < 6 ||
    segments[0] !== '' ||
    segments[3] !== 'resolve' ||
    segments.slice(1).some((segment) => segment.length === 0 || /%2f|%5c/i.test(segment)) ||
    !segments.at(-1)!.endsWith('.gguf')
  ) throw invalid();
  return value;
}

function safeFilename(value: unknown): string {
  return patternString(value, /^[A-Za-z0-9][A-Za-z0-9._+-]{0,255}$/);
}

function safeText(value: unknown, limit: number): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > limit || /[\0-\x1f\x7f]/.test(value)) throw invalid();
  return value;
}

function safeTextAllowEmpty(value: unknown, limit: number): string {
  if (typeof value !== 'string' || value.length > limit || /[\0-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value)) throw invalid();
  return value;
}

function nullableSafeText(value: unknown, limit: number): string | null {
  return value === null ? null : safeText(value, limit);
}

function patternString(value: unknown, pattern: RegExp): string {
  if (typeof value !== 'string' || !pattern.test(value)) throw invalid();
  return value;
}

function nullablePattern(value: unknown, pattern: RegExp): string | null {
  return value === null ? null : patternString(value, pattern);
}

function nullableHash(value: unknown): string | null {
  return value === null ? null : validateHash(value);
}

function positiveSafeInteger(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) throw invalid();
  return value;
}

function nonNegativeSafeInteger(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw invalid();
  return value;
}

function boundedNonNegativeInteger(value: unknown, maximum: number): number {
  const integer = nonNegativeSafeInteger(value);
  if (integer > maximum) throw invalid();
  return integer;
}

function boundedArray(value: unknown, limit: number): readonly unknown[] {
  if (!Array.isArray(value) || value.length > limit) throw invalid();
  return value;
}

function validateUnique(values: readonly string[]): void {
  if (new Set(values).size !== values.length) throw invalid();
}

function validateUniqueSorted(values: readonly string[]): void {
  validateUnique(values);
  if (values.some((value, index) => index > 0 && values[index - 1]! > value)) throw invalid();
}

function exactString<const T extends string>(value: unknown, options: readonly T[]): T {
  if (typeof value !== 'string' || !options.includes(value as T)) throw invalid();
  return value as T;
}

function exactBoolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw invalid();
  return value;
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

function validateChatSessionId(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(value)) throw invalid();
  return value;
}

function validateMaxTokens(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1 || value > 512) throw invalid();
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

function expectExactRecord(value: unknown, expectedKeys: readonly string[]): Readonly<Record<string, unknown>> {
  const object = expectRecord(value);
  const actual = Object.keys(object).sort();
  const expected = [...expectedKeys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) throw invalid();
  return object;
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
