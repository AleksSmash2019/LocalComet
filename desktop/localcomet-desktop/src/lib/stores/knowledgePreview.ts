import { get, writable } from 'svelte/store';
import { cancelTurn } from '$lib/bridge/controlPlane';
import {
  decideKnowledgeTurn,
  requestKnowledgePreview,
  subscribeKnowledgeInjectionEvents
} from '$lib/bridge/knowledge';
import {
  DEFAULT_KNOWLEDGE_CONTEXT_CHARS,
  DEFAULT_KNOWLEDGE_INTENT,
  DEFAULT_KNOWLEDGE_RESULTS
} from '$lib/knowledge/knowledgePreview';
import type {
  KnowledgeAction,
  KnowledgePreview,
  KnowledgeUiState
} from '$lib/knowledge/knowledgePreview';
import { startLocalModelTurn } from '$lib/stores/modelGateway';

export interface KnowledgePreviewState {
  readonly enabled: boolean;
  readonly lifecycle: KnowledgeUiState;
  readonly turnId: string | null;
  readonly pendingPrompt: string;
  readonly preview: KnowledgePreview | null;
  readonly expandedSourceIds: readonly string[];
  readonly lastError: { readonly code: string; readonly message: string } | null;
}

const initialState: KnowledgePreviewState = {
  enabled: false,
  lifecycle: 'OFF',
  turnId: null,
  pendingPrompt: '',
  preview: null,
  expandedSourceIds: [],
  lastError: null
};

let unsubscribeEvents: (() => void) | null = null;

export const knowledgePreviewStore = writable<KnowledgePreviewState>(initialState);

export function setProjectKnowledgeEnabled(enabled: boolean): void {
  const state = get(knowledgePreviewStore);
  if (isDecisionLocked(state.lifecycle)) return;
  knowledgePreviewStore.set(
    enabled
      ? { ...initialState, enabled: true }
      : initialState
  );
}

export async function prepareProjectKnowledge(turnId: string, prompt: string): Promise<boolean> {
  const current = get(knowledgePreviewStore);
  if (!current.enabled || isDecisionLocked(current.lifecycle)) return false;
  knowledgePreviewStore.set({
    enabled: true,
    lifecycle: 'RETRIEVING',
    turnId,
    pendingPrompt: prompt,
    preview: null,
    expandedSourceIds: current.expandedSourceIds,
    lastError: null
  });
  try {
    const response = await requestKnowledgePreview({
      turnId,
      intent: DEFAULT_KNOWLEDGE_INTENT,
      maxContextChars: DEFAULT_KNOWLEDGE_CONTEXT_CHARS,
      maxResults: DEFAULT_KNOWLEDGE_RESULTS
    });
    if (response.state === 'FAILED') {
      knowledgePreviewStore.update((state) => ({
        ...state,
        lifecycle: 'FAILED',
        lastError: { code: response.error.code, message: response.error.safe_message }
      }));
      return false;
    }
    knowledgePreviewStore.update((state) => ({
      ...state,
      lifecycle: 'PREVIEW_READY',
      preview: response,
      lastError: null
    }));
    return true;
  } catch (error) {
    const normalized = normalizeError(error);
    knowledgePreviewStore.update((state) => ({ ...state, lifecycle: 'FAILED', lastError: normalized }));
    return false;
  }
}

export async function retryProjectKnowledgePreview(): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  if (!state.turnId || !state.pendingPrompt || !['FAILED', 'STALE'].includes(state.lifecycle)) return false;
  return prepareProjectKnowledge(state.turnId, state.pendingPrompt);
}

export async function decideProjectKnowledge(action: KnowledgeAction): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  const preview = state.preview;
  if (!preview || state.lifecycle !== 'PREVIEW_READY') return false;
  knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'DECIDING', lastError: null }));
  try {
    const response = await decideKnowledgeTurn({
      turnId: preview.turn_id,
      injectionId: preview.injection_id,
      expectedPreviewHash: preview.preview_hash,
      action
    });
    knowledgePreviewStore.update((current) => ({
      ...current,
      lifecycle:
        response.state === 'STALE'
          ? 'STALE'
          : action === 'INCLUDE_AND_SEND'
            ? response.state === 'INJECTED' ? 'INJECTED' : 'DISPATCHING'
            : action === 'CANCEL' ? 'CANCELLED' : 'REJECTED',
      lastError: response.error
        ? { code: response.error.code, message: response.error.safe_message }
        : null
    }));
    return response.state !== 'STALE';
  } catch (error) {
    knowledgePreviewStore.update((current) => ({
      ...current,
      lifecycle: 'FAILED',
      lastError: normalizeError(error)
    }));
    return false;
  }
}

export async function cancelProjectKnowledge(): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  if (state.preview && state.lifecycle === 'PREVIEW_READY') {
    return decideProjectKnowledge('CANCEL');
  }
  if (!state.turnId || !['FAILED', 'STALE'].includes(state.lifecycle)) return false;
  try {
    await cancelTurn(state.turnId, 'user_requested');
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'CANCELLED', lastError: null }));
    return true;
  } catch (error) {
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'FAILED', lastError: normalizeError(error) }));
    return false;
  }
}

export async function sendWithoutKnowledgeAfterFailure(): Promise<boolean> {
  const state = get(knowledgePreviewStore);
  if (!state.turnId || !state.pendingPrompt || !['FAILED', 'STALE'].includes(state.lifecycle)) return false;
  try {
    await cancelTurn(state.turnId, 'user_requested');
    await startLocalModelTurn(state.pendingPrompt);
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'REJECTED', lastError: null }));
    return true;
  } catch (error) {
    knowledgePreviewStore.update((current) => ({ ...current, lifecycle: 'FAILED', lastError: normalizeError(error) }));
    return false;
  }
}

export function toggleKnowledgeSource(noteId: string): void {
  knowledgePreviewStore.update((state) => {
    const expanded = new Set(state.expandedSourceIds);
    if (expanded.has(noteId)) expanded.delete(noteId);
    else expanded.add(noteId);
    return { ...state, expandedSourceIds: [...expanded] };
  });
}

export async function initializeKnowledgePreviewEvents(): Promise<void> {
  if (unsubscribeEvents) return;
  unsubscribeEvents = await subscribeKnowledgeInjectionEvents((injectionId) => {
    knowledgePreviewStore.update((state) =>
      state.preview?.injection_id === injectionId
        ? { ...state, lifecycle: 'INJECTED', lastError: null }
        : state
    );
  });
}

export function shutdownKnowledgePreviewEvents(): void {
  unsubscribeEvents?.();
  unsubscribeEvents = null;
}

export function resetKnowledgePreviewStore(): void {
  unsubscribeEvents = null;
  knowledgePreviewStore.set(initialState);
}

function isDecisionLocked(state: KnowledgeUiState): boolean {
  return ['RETRIEVING', 'PREVIEW_READY', 'DECIDING', 'DISPATCHING'].includes(state);
}

function normalizeError(error: unknown): { code: string; message: string } {
  if (typeof error === 'object' && error !== null) {
    const record = error as Record<string, unknown>;
    return {
      code: String(record.code ?? 'knowledge_error').slice(0, 64),
      message: String(record.message ?? 'Project knowledge request failed').slice(0, 240)
    };
  }
  return { code: 'knowledge_error', message: 'Project knowledge request failed' };
}
