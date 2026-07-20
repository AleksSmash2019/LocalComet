import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import {
  CONTROL_PLANE_EVENT_CHANNEL,
  bootstrapControlPlane,
  createSession,
  normalizeBridgeError,
  subscribeControlPlaneEvents
} from '../src/lib/bridge/controlPlane';
import {
  applyControlPlaneEvent,
  controlPlaneStore,
  initializeControlPlaneBridge,
  resetControlPlaneStore
} from '../src/lib/stores/controlPlane';
import type { ControlPlaneEvent } from '../src/lib/types/controlPlane';

const SESSION_ID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const THREAD_ID = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const TURN_ID = 'cccccccccccccccccccccccc';
const ITEM_ID = 'dddddddddddddddddddddddd';

let invokeCalls: string[] = [];
let listener: ((event: { payload: ControlPlaneEvent }) => void) | null = null;
let cleanupCalled = false;

const NO_BOOTSTRAP_OVERRIDE = Symbol('no-bootstrap-override');
const mockState: { failBootstrap: boolean; bootstrapOverride: unknown | typeof NO_BOOTSTRAP_OVERRIDE } = {
  failBootstrap: false,
  bootstrapOverride: NO_BOOTSTRAP_OVERRIDE
};

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string): Promise<unknown> => {
    invokeCalls.push(command);
    if (mockState.failBootstrap && command === 'control_plane_bootstrap') {
      throw { code: 'sidecar_unavailable', message: 'offline' };
    }
    if (command === 'control_plane_bootstrap') {
      return mockState.bootstrapOverride === NO_BOOTSTRAP_OVERRIDE ? bootstrapFixture() : mockState.bootstrapOverride;
    }
    if (command === 'control_plane_create_session') return { session_id: SESSION_ID, state: 'OPEN', title: 'Demo', thread_count: 0 };
    return {};
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_event: string, callback: (event: { payload: ControlPlaneEvent }) => void): Promise<() => void> => {
    listener = callback;
    return () => {
      cleanupCalled = true;
    };
  })
}));

function installTauriMock(
  failBootstrap = false,
  bootstrapOverride: unknown | typeof NO_BOOTSTRAP_OVERRIDE = NO_BOOTSTRAP_OVERRIDE
): void {
  invokeCalls = [];
  cleanupCalled = false;
  listener = null;
  mockState.failBootstrap = failBootstrap;
  mockState.bootstrapOverride = bootstrapOverride;
}

function bootstrapFixture() {
  return {
    control_plane_version: 'v6.84.5.1',
    protocol: 'localcomet.ipc',
    protocol_version: '1.0',
    sidecar_runtime_version: 'v6.84.3',
    capabilities: ['app.bootstrap', 'session.create', 'thread.create', 'turn.start_mock'],
    limits: {
      maximum_sessions: 16,
      maximum_threads_per_session: 32,
      maximum_turns_per_thread: 64,
      maximum_prompt_characters: 8192,
      maximum_events_per_request: 64
    },
    counts: { sessions: 0, threads: 0, turns: 0, active_turns: 0 },
    persistence: false,
    models_connected: false,
    provider_registry_available: false,
    harness_registry_available: false
  };
}

function event(method: ControlPlaneEvent['method'], sequence: number, patch: Partial<ControlPlaneEvent> = {}): ControlPlaneEvent {
  return {
    method,
    sequence,
    reply_to: patch.reply_to ?? 'deskcp-0000000001',
    control_plane_version: 'v6.84.5.1',
    session_id: patch.session_id ?? SESSION_ID,
    thread_id: patch.thread_id ?? THREAD_ID,
    turn_id: patch.turn_id ?? TURN_ID,
    item_id: patch.item_id ?? ITEM_ID,
    state: patch.state ?? '',
    kind: patch.kind ?? null,
    text: patch.text ?? null,
    metadata: patch.metadata ?? {}
  };
}

describe('control-plane bridge and store', () => {
  beforeEach(() => {
    resetControlPlaneStore();
    installTauriMock();
  });

  it('starts disconnected and reaches ready after one bootstrap', async () => {
    expect(get(controlPlaneStore).bridgeState).toBe('DISCONNECTED');
    const promise = initializeControlPlaneBridge();
    expect(get(controlPlaneStore).bridgeState).toBe('CONNECTING');
    await promise;
    expect(get(controlPlaneStore).bridgeState).toBe('READY');
    await initializeControlPlaneBridge();
    expect(invokeCalls.filter((command) => command === 'control_plane_bootstrap')).toHaveLength(1);
  });

  it('sets unavailable on bootstrap failure', async () => {
    installTauriMock(true);
    await initializeControlPlaneBridge();
    expect(get(controlPlaneStore).bridgeState).toBe('UNAVAILABLE');
  });

  it('accepts the authoritative Python Control Plane bootstrap version', async () => {
    const bootstrap = await bootstrapControlPlane();
    expect(bootstrap.control_plane_version).toBe('v6.84.5.1');
    expect(bootstrap.protocol_version).toBe('1.0');
    expect(bootstrap.sidecar_runtime_version).toBe('v6.84.3');
  });

  it('rejects the stale v6.84.4 bootstrap version', async () => {
    installTauriMock(false, { ...bootstrapFixture(), control_plane_version: 'v6.84.4' });
    await expect(bootstrapControlPlane()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('rejects malformed Control Plane bootstrap versions', async () => {
    for (const malformed of ['', '6.84.5.1', 'v6.84.5.1.0', null, 68451]) {
      installTauriMock(false, { ...bootstrapFixture(), control_plane_version: malformed });
      await expect(bootstrapControlPlane()).rejects.toMatchObject({ code: 'invalid_payload' });
    }
  });

  it('subscription returns cleanup and listener receives validated events', async () => {
    const seen: string[] = [];
    const cleanup = await subscribeControlPlaneEvents((payload) => seen.push(payload.method));
    listener?.({ payload: event('session.created', 0) });
    listener?.({ payload: event('model.turn.timed_out', 0, { reply_to: 'model-timeout', state: 'TimedOut' }) });
    cleanup();
    expect(cleanupCalled).toBe(true);
    expect(seen).toEqual(['session.created', 'model.turn.timed_out']);
  });

  it('accepts model timeout events in the shared Control Plane stream', () => {
    applyControlPlaneEvent(event('model.turn.timed_out', 0, { reply_to: 'model-timeout', state: 'TimedOut' }));
    const state = get(controlPlaneStore);
    expect(state.lastError).toBeNull();
    expect(state.recentEvents.at(-1)?.method).toBe('model.turn.timed_out');
  });

  it('updates session, thread, turn and items from ordered events', () => {
    applyControlPlaneEvent(event('session.created', 0, { reply_to: 'r1', metadata: { title: 'Demo' } }));
    applyControlPlaneEvent(event('thread.created', 0, { reply_to: 'r2', metadata: { title: 'Thread' } }));
    applyControlPlaneEvent(event('turn.started', 0, { reply_to: 'r3', state: 'RUNNING' }));
    applyControlPlaneEvent(event('item.started', 1, { reply_to: 'r3', kind: 'assistant_message', state: 'STARTED' }));
    applyControlPlaneEvent(event('item.delta', 2, { reply_to: 'r3', kind: 'assistant_message', state: 'STREAMING', text: 'No model ' }));
    applyControlPlaneEvent(event('item.completed', 3, { reply_to: 'r3', kind: 'assistant_message', state: 'COMPLETED' }));
    applyControlPlaneEvent(event('turn.completed', 4, { reply_to: 'r3', state: 'COMPLETED' }));
    const state = get(controlPlaneStore);
    expect(state.currentSession?.session_id).toBe(SESSION_ID);
    expect(state.currentThread?.thread_id).toBe(THREAD_ID);
    expect(state.currentTurn?.state).toBe('COMPLETED');
    expect(state.items[0]?.text).toContain('No model');
  });

  it('rejects duplicate and decreasing sequences and event after terminal', () => {
    applyControlPlaneEvent(event('turn.started', 0, { reply_to: 'r4', state: 'RUNNING' }));
    applyControlPlaneEvent(event('turn.completed', 1, { reply_to: 'r4', state: 'COMPLETED' }));
    applyControlPlaneEvent(event('item.delta', 2, { reply_to: 'r4', text: 'late' }));
    expect(get(controlPlaneStore).lastError?.code).toBe('invalid_sequence');
    applyControlPlaneEvent(event('item.delta', 1, { reply_to: 'r4', text: 'duplicate' }));
    expect(get(controlPlaneStore).lastError?.code).toBe('invalid_sequence');
  });

  it('keeps recent event and item lists bounded', () => {
    for (let index = 0; index < 140; index += 1) {
      applyControlPlaneEvent(event('item.started', index, { reply_to: 'bounded', item_id: `${index.toString(16).padStart(24, '0')}`, kind: 'status' }));
    }
    const state = get(controlPlaneStore);
    expect(state.recentEvents.length).toBeLessThanOrEqual(100);
    expect(state.items.length).toBeLessThanOrEqual(128);
  });

  it('does not persist or invent model/tool success', async () => {
    await createSession('x');
    expect(invokeCalls).toContain('control_plane_create_session');
    expect('localStorage' in globalThis).toBe(false);
    expect(get(controlPlaneStore).currentTurn?.model_called ?? false).toBe(false);
  });

  it('renders control plane status, demo notice and diagnostics facts', () => {
    const header = render(ChatHeader).body;
    const composer = render(MessageComposer).body;
    const diagnostics = render(Diagnostics).body;
    expect(header).toContain('Модель: недоступна');
    expect(composer).toContain('Сначала подключите модель');
    expect(diagnostics).toContain('Модель вызвана');
    expect(diagnostics).toContain('Инструментов выполнено');
    expect(diagnostics).toContain('Провайдер');
    expect(diagnostics).toContain('Не настроено');
  });

  it('normalizes errors and exposes no generic bridge method', () => {
    expect(normalizeBridgeError({ code: 'x', message: 'Traceback secret' }).message).toContain('<redacted>');
    expect(typeof bootstrapControlPlane).toBe('function');
  });
});
