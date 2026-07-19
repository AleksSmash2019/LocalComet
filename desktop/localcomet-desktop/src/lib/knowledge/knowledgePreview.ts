export type KnowledgeIntent =
  | 'AUTO'
  | 'CURRENT_STATE'
  | 'ARCHITECTURE'
  | 'SECURITY'
  | 'HISTORY'
  | 'FOUNDER_INTENT'
  | 'ROADMAP'
  | 'RESEARCH'
  | 'OPERATIONAL'
  | 'INCIDENT';

export type KnowledgeAction =
  | 'INCLUDE_AND_SEND'
  | 'REJECT_AND_SEND_WITHOUT_KNOWLEDGE'
  | 'CANCEL';

export type KnowledgeUiState =
  | 'OFF'
  | 'RETRIEVING'
  | 'PREVIEW_READY'
  | 'DECIDING'
  | 'DISPATCHING'
  | 'INJECTED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'FAILED'
  | 'STALE';

export interface KnowledgePreviewSection {
  readonly heading: string;
  readonly line_start: number;
  readonly line_end: number;
  readonly content: string;
}

export interface KnowledgePreviewSource {
  readonly note_id: string;
  readonly title: string;
  readonly relative_path: string;
  readonly knowledge_layer: string;
  readonly evidence_class: string;
  readonly authority: string;
  readonly status: string;
  readonly canonical: boolean;
  readonly selected_sections: readonly KnowledgePreviewSection[];
}

export interface KnowledgePreview {
  readonly state: 'PREVIEW_READY';
  readonly turn_id: string;
  readonly request_id: string;
  readonly injection_id: string;
  readonly bundle_id: string;
  readonly preview_hash: string;
  readonly vault_revision: string;
  readonly resolved_intent: KnowledgeIntent;
  readonly source_count: number;
  readonly total_chars: number;
  readonly truncated: boolean;
  readonly sources: readonly KnowledgePreviewSource[];
  readonly model_dispatched: false;
  readonly tools_executed: 0;
}

export interface KnowledgePreviewFailure {
  readonly state: 'FAILED';
  readonly turn_id: string;
  readonly request_id?: string;
  readonly injection_id: null;
  readonly error: { readonly code: string; readonly safe_message: string };
  readonly model_dispatched: false;
  readonly tools_executed: 0;
}

export interface KnowledgeDecisionResponse {
  readonly state: 'DECIDING' | 'DISPATCHING' | 'INJECTED' | 'REJECTED' | 'STALE';
  readonly turn_id: string;
  readonly injection_id: string;
  readonly action?: KnowledgeAction;
  readonly preview_hash?: string;
  readonly decision_source?: 'USER_APPROVAL';
  readonly model_turn_id?: string | null;
  readonly model_dispatched: boolean;
  readonly knowledge_included?: boolean;
  readonly duplicate?: boolean;
  readonly error?: { readonly code: string; readonly safe_message: string };
}

export const DEFAULT_KNOWLEDGE_INTENT: KnowledgeIntent = 'AUTO';
export const DEFAULT_KNOWLEDGE_CONTEXT_CHARS = 12_000;
export const DEFAULT_KNOWLEDGE_RESULTS = 8;

export function abbreviateKnowledgeHash(value: string): string {
  const hex = value.startsWith('sha256:') ? value.slice(7) : value;
  return `${hex.slice(0, 8)}…`;
}
