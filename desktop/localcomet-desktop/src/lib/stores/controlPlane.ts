import { get, writable } from 'svelte/store';
import {
  bootstrapControlPlane,
  cancelTurn,
  createSession,
  createThread,
  getTurnStatus,
  normalizeBridgeError,
  startMockTurn,
  subscribeControlPlaneEvents
} from '$lib/bridge/controlPlane';
import type {
  BootstrapResponse,
  BridgeState,
  CancelReason,
  ControlPlaneEvent,
  ControlPlaneItem,
  MockTurnBehavior,
  SanitizedBridgeError,
  SessionSummary,
  ThreadSummary,
  TurnSummary
} from '$lib/types/controlPlane';

export const MAX_RECENT_EVENTS = 100;
export const MAX_ITEMS = 128;
export const MAX_ITEM_TEXT = 65_536;

interface ControlPlaneState {
  readonly bridgeState: BridgeState;
  readonly bootstrap: BootstrapResponse | null;
  readonly currentSession: SessionSummary | null;
  readonly currentThread: ThreadSummary | null;
  readonly currentTurn: TurnSummary | null;
  readonly items: readonly ControlPlaneItem[];
  readonly recentEvents: readonly ControlPlaneEvent[];
  readonly lastError: SanitizedBridgeError | null;
  readonly initialized: boolean;
  readonly eventCount: number;
}

const initialState: ControlPlaneState = {
  bridgeState: 'DISCONNECTED',
  bootstrap: null,
  currentSession: null,
  currentThread: null,
  currentTurn: null,
  items: [],
  recentEvents: [],
  lastError: null,
  initialized: false,
  eventCount: 0
};

const lastSequenceByReplyTo = new Map<string, number>();
let unsubscribeEvents: (() => void) | null = null;
let bootstrapStarted = false;

export const controlPlaneStore = writable<ControlPlaneState>(initialState);

export async function initializeControlPlaneBridge(): Promise<void> {
  if (bootstrapStarted) return;
  bootstrapStarted = true;
  controlPlaneStore.update((state) => ({ ...state, bridgeState: 'CONNECTING', initialized: true }));
  try {
    unsubscribeEvents = await subscribeControlPlaneEvents(applyControlPlaneEvent);
    const bootstrap = await bootstrapControlPlane();
    controlPlaneStore.update((state) => ({ ...state, bridgeState: 'READY', bootstrap, lastError: null }));
  } catch (error) {
    const normalized = normalizeBridgeError(error);
    controlPlaneStore.update((state) => ({
      ...state,
      bridgeState: normalized.code === 'sidecar_unavailable' ? 'UNAVAILABLE' : 'ERROR',
      lastError: normalized
    }));
  }
}

export function shutdownControlPlaneBridge(): void {
  unsubscribeEvents?.();
  unsubscribeEvents = null;
}

export async function submitControlPlaneDemo(prompt: string, behavior: MockTurnBehavior = 'complete'): Promise<boolean> {
  const state = get(controlPlaneStore);
  if (state.bridgeState !== 'READY') return false;
  try {
    let session = state.currentSession;
    if (!session) {
      session = await createSession('LocalComet demo');
      controlPlaneStore.update((current) => ({ ...current, currentSession: session }));
    }
    let thread = get(controlPlaneStore).currentThread;
    if (!thread) {
      thread = await createThread(session.session_id, 'Control Plane demo');
      controlPlaneStore.update((current) => ({ ...current, currentThread: thread }));
    }
    const turn = await startMockTurn(thread.thread_id, prompt, behavior);
    controlPlaneStore.update((current) => ({ ...current, currentTurn: turn, lastError: null }));
    if (turn.state === 'RUNNING') {
      const refreshed = await getTurnStatus(turn.turn_id);
      controlPlaneStore.update((current) => ({ ...current, currentTurn: refreshed }));
    }
    return true;
  } catch (error) {
    controlPlaneStore.update((current) => ({ ...current, bridgeState: 'ERROR', lastError: normalizeBridgeError(error) }));
    return false;
  }
}

export async function createPendingKnowledgeTurn(prompt: string): Promise<TurnSummary | null> {
  const state = get(controlPlaneStore);
  if (state.bridgeState !== 'READY') return null;
  try {
    let session = state.currentSession;
    if (!session) {
      session = await createSession('LocalComet chat');
      controlPlaneStore.update((current) => ({ ...current, currentSession: session }));
    }
    let thread = get(controlPlaneStore).currentThread;
    if (!thread) {
      thread = await createThread(session.session_id, 'Project Knowledge');
      controlPlaneStore.update((current) => ({ ...current, currentThread: thread }));
    }
    const turn = await startMockTurn(thread.thread_id, prompt, 'pending_model');
    controlPlaneStore.update((current) => ({ ...current, currentTurn: turn, lastError: null }));
    return turn;
  } catch (error) {
    controlPlaneStore.update((current) => ({ ...current, lastError: normalizeBridgeError(error) }));
    return null;
  }
}

export async function startCancellationDemo(): Promise<void> {
  await submitControlPlaneDemo('Cancellation demo request', 'wait_for_cancel');
}

export async function cancelCurrentDemoTurn(reason: CancelReason = 'user_requested'): Promise<void> {
  const turn = get(controlPlaneStore).currentTurn;
  if (!turn || turn.state !== 'RUNNING') return;
  try {
    const cancelled = await cancelTurn(turn.turn_id, reason);
    controlPlaneStore.update((state) => ({ ...state, currentTurn: cancelled, lastError: null }));
  } catch (error) {
    controlPlaneStore.update((state) => ({ ...state, lastError: normalizeBridgeError(error) }));
  }
}

export function resetControlPlaneStore(): void {
  lastSequenceByReplyTo.clear();
  bootstrapStarted = false;
  unsubscribeEvents = null;
  controlPlaneStore.set(initialState);
}

export function applyControlPlaneEvent(event: ControlPlaneEvent): void {
  if (!validEventSequence(event)) return;
  controlPlaneStore.update((state) => {
    if (isTerminalLocked(state, event)) {
      return { ...state, lastError: { code: 'invalid_sequence', message: 'Event after terminal turn rejected' } };
    }
    const recentEvents = [...state.recentEvents, event].slice(-MAX_RECENT_EVENTS);
    let next: ControlPlaneState = {
      ...state,
      recentEvents,
      eventCount: state.eventCount + 1,
      lastError: null
    };
    if (event.method === 'session.created' && event.session_id) {
      next = {
        ...next,
        currentSession: {
          session_id: event.session_id,
          state: 'OPEN',
          title: String(event.metadata.title ?? ''),
          thread_count: 0
        }
      };
    }
    if (event.method === 'thread.created' && event.thread_id && event.session_id) {
      next = {
        ...next,
        currentThread: {
          thread_id: event.thread_id,
          session_id: event.session_id,
          state: 'ACTIVE',
          title: String(event.metadata.title ?? ''),
          turn_count: 0,
          active_turn_id: null
        }
      };
    }
    if (event.method === 'turn.started' && event.turn_id) {
      next = {
        ...next,
        currentTurn: {
          turn_id: event.turn_id,
          thread_id: event.thread_id ?? undefined,
          state: 'RUNNING',
          model_called: false,
          tools_executed: 0
        },
        items: []
      };
    }
    if (event.method === 'turn.completed' && next.currentTurn) {
      next = { ...next, currentTurn: { ...next.currentTurn, state: 'COMPLETED', model_called: false, tools_executed: 0 } };
    }
    if (event.method === 'turn.cancelled' && next.currentTurn) {
      next = { ...next, currentTurn: { ...next.currentTurn, state: 'CANCELLED', model_called: false, tools_executed: 0 } };
    }
    if (event.method === 'item.started' && event.item_id && event.kind) {
      next = {
        ...next,
        items: [...next.items, { item_id: event.item_id, kind: event.kind, state: 'STARTED' as const, text: '' }].slice(-MAX_ITEMS)
      };
    }
    if (event.method === 'item.delta' && event.item_id && event.text) {
      next = {
        ...next,
        items: next.items.map((item) =>
          item.item_id === event.item_id
            ? { ...item, state: 'STREAMING', text: `${item.text}${event.text ?? ''}`.slice(0, MAX_ITEM_TEXT) }
            : item
        )
      };
    }
    if (event.method === 'item.completed' && event.item_id) {
      next = {
        ...next,
        items: next.items.map((item) =>
          item.item_id === event.item_id
            ? { ...item, state: 'COMPLETED', text: event.text ? `${item.text}${event.text}`.slice(0, MAX_ITEM_TEXT) : item.text }
            : item
        )
      };
    }
    return next;
  });
}

function validEventSequence(event: ControlPlaneEvent): boolean {
  const last = lastSequenceByReplyTo.get(event.reply_to);
  if (last !== undefined && event.sequence <= last) {
    controlPlaneStore.update((state) => ({ ...state, lastError: { code: 'invalid_sequence', message: 'Duplicate or decreasing event sequence rejected' } }));
    return false;
  }
  if (!isKnownEvent(event.method)) {
    controlPlaneStore.update((state) => ({ ...state, lastError: { code: 'unsupported_method', message: 'Unknown event rejected' } }));
    return false;
  }
  lastSequenceByReplyTo.set(event.reply_to, event.sequence);
  return true;
}

function isTerminalLocked(state: ControlPlaneState, event: ControlPlaneEvent): boolean {
  const turn = state.currentTurn;
  if (!turn || !event.turn_id || turn.turn_id !== event.turn_id) return false;
  return ['COMPLETED', 'CANCELLED', 'FAILED'].includes(turn.state) && !['turn.completed', 'turn.cancelled', 'turn.failed'].includes(event.method);
}

function isKnownEvent(method: string): boolean {
  return [
    'sidecar.status',
    'session.created',
    'session.closed',
    'thread.created',
    'turn.started',
    'turn.completed',
    'turn.cancelled',
    'turn.failed',
    'item.started',
    'item.delta',
    'item.completed',
    'model.turn.started',
    'model.output.delta',
    'model.turn.completed',
    'model.turn.cancelled',
    'model.turn.failed'
  ].includes(method);
}
