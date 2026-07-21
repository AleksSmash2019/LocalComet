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
