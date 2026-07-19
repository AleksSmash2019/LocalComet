export type ProviderId = 'openai-compatible-local' | 'managed-llama-cpp';
export type HarnessId = 'minimal' | 'native-localcomet';
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
  readonly turn_id: string;
  readonly state: 'GENERATING';
  readonly provider_id: ProviderId;
  readonly harness_id: HarnessId;
  readonly model_id: string;
  readonly binding_fingerprint: string;
  readonly model_called: false;
  readonly tools_executed: 0;
  readonly persistence: false;
}

export type ModelEventMethod =
  | 'model.turn.started'
  | 'model.output.delta'
  | 'model.turn.completed'
  | 'model.turn.cancelled'
  | 'model.turn.failed';

export interface ModelGatewayEvent {
  readonly method: ModelEventMethod;
  readonly sequence: number;
  readonly reply_to: string;
  readonly turn_id: string;
  readonly state: GatewayStatus;
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

export interface ManagedRuntimeStatus {
  readonly engine: 'llama.cpp';
  readonly state: ManagedRuntimeState;
  readonly installation: 'Installed' | 'Not installed' | string;
  readonly runtime_version: string | null;
  readonly runtime_instance_id: string | null;
  readonly runtime_instance_fingerprint: string | null;
  readonly model_id: string | null;
  readonly model_display_name: string | null;
  readonly binding_fingerprint: string | null;
  readonly last_error: string | null;
}

export interface ManagedModelEntry {
  readonly model_id: string;
  readonly display_name: string;
  readonly size_bytes: number;
  readonly availability: 'Available' | string;
  readonly identity_fingerprint: string;
}

export interface ManagedModelCatalog {
  readonly engine: 'llama.cpp';
  readonly model_root: '<MODEL_ROOT>';
  readonly models: readonly ManagedModelEntry[];
  readonly maximum_models: 64;
}

export interface ManagedRuntimeStartResponse {
  readonly state: 'Ready';
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
