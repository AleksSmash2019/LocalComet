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
