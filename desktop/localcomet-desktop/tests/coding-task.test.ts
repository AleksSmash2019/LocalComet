import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CodingTaskStore } from '$lib/stores/codingTask';

const invokeMocks = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => invokeMocks);

/** Wire shape mirrors the Rust ApprovalEnvelope serde camelCase rename. */
const envelope = {
  token: 'lcap_test_token',
  approvalId: 'apid_1',
  callId: 'cid_1'
};

const okResponse = {
  task_id: 'task_x',
  status: 'behavior_verified' as const,
  verification_level: 'behavior_verified' as const,
  applied_paths: ['calc.rs'],
  error_diagnostics: 0,
  generation_hash: 'gh',
  test_exit_code: 0,
  reason: 'clean diagnostics and focused test',
  grant_id: 'gr_1',
  approval_consumed: true
};

/** Route mocks by command name: approval mint always precedes start. */
function routeByCommand(handler: (cmd: string) => unknown | Promise<unknown>) {
  invokeMocks.invoke.mockImplementation(async (cmd: string) => handler(cmd));
}

describe('CodingTaskStore', () => {
  beforeEach(() => {
    invokeMocks.invoke.mockReset();
  });

  it('start mints a one-time grant before coding_start and completes only from backend truth', async () => {
    const calls: string[] = [];
    routeByCommand((cmd) => {
      calls.push(cmd);
      if (cmd === 'coding_start_approval') return envelope;
      return okResponse;
    });
    const store = new CodingTaskStore();
    const pending = store.start('C:\\ws', 'calc.rs', 'fn x() {}');
    expect(store.status).toBe('starting');
    await pending;
    expect(store.status).toBe('completed');
    expect(calls[0]).toBe('coding_start_approval');
    expect(calls[1]).toBe('coding_start');
    // The start request carries the minted one-time material.
    const startArgs = invokeMocks.invoke.mock.calls.find(
      (c: unknown[]) => c[0] === 'coding_start'
    ) as [string, { request: Record<string, unknown> }];
    expect(startArgs[1].request.token).toBe(envelope.token);
    expect(startArgs[1].request.approvalId).toBe(envelope.approvalId);
    expect(startArgs[1].request.callId).toBe(envelope.callId);
    expect(store.lastResult?.approval_consumed).toBe(true);
  });

  it('grant denial surfaces as typed error without calling coding_start', async () => {
    const calls: string[] = [];
    routeByCommand((cmd) => {
      calls.push(cmd);
      if (cmd === 'coding_start_approval') throw { code: 'permission_denied' };
      return okResponse;
    });
    const store = new CodingTaskStore();
    await store.start('C:\\ws', '../evil.rs', 'x');
    expect(store.status).toEqual({ error: 'permission_denied' });
    expect(calls).toEqual(['coding_start_approval']);
  });

  it('start failure maps to failed with bounded message', async () => {
    routeByCommand((cmd) => {
      if (cmd === 'coding_start_approval') return envelope;
      throw { code: 'invalid_patch_path', message: 'bad path' };
    });
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    expect(store.status).toEqual({ error: 'bad path' });
  });

  it('blocked backend result stays blocked, never completed', async () => {
    routeByCommand((cmd) =>
      cmd === 'coding_start_approval'
        ? envelope
        : { ...okResponse, status: 'blocked', reason: 'conflict' }
    );
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    expect(store.status).toBe('blocked');
  });

  it('compile-only outcome is visibly distinct from full success (P1)', async () => {
    routeByCommand((cmd) =>
      cmd === 'coding_start_approval'
        ? envelope
        : {
            ...okResponse,
            status: 'compile_verified_only',
            verification_level: 'compile_verified_only',
            test_exit_code: null,
            reason: 'focused test unavailable; behavior NOT verified'
          }
    );
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    // compile-only must NEVER surface as 'completed'.
    expect(store.status).toBe('compile_verified_only');
    expect(store.status).not.toBe('completed');
    expect(store.lastResult?.test_exit_code).toBeNull();
  });

  it('paused_for_review surfaces as its own truthful state', async () => {
    routeByCommand((cmd) =>
      cmd === 'coding_start_approval'
        ? envelope
        : { ...okResponse, status: 'paused_for_review', reason: 'rollback conflicted' }
    );
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    expect(store.status).toBe('paused_for_review');
  });

  it('cancel before completion marks cancelled and does not fake completed', async () => {
    let releaseStart!: (v: unknown) => void;
    const startGate = new Promise((resolve) => {
      releaseStart = resolve;
    });
    routeByCommand((cmd) => {
      if (cmd === 'coding_start_approval') return envelope;
      if (cmd === 'coding_cancel') return { cancel_requested: true };
      return startGate;
    });
    const store = new CodingTaskStore();
    const pending = store.start('C:\\ws', 'a.rs', 'x');
    await store.cancel();
    releaseStart(okResponse);
    await pending;
    expect(store.status).toBe('cancelled');
  });

  it('cancel on finished task is a typed no-op', async () => {
    routeByCommand((cmd) => {
      if (cmd === 'coding_start_approval') return envelope;
      if (cmd === 'coding_cancel') return { cancel_requested: false, reason: 'task_not_running' };
      return okResponse;
    });
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    await store.cancel();
    expect(store.status).toBe('completed');
  });

  it('refreshPersistedTasks loads bounded workspace task inventory', async () => {
    routeByCommand((cmd) =>
      cmd === 'coding_list_tasks'
        ? {
            workspace_digest: 'ws_digest',
            tasks: [
              {
                task_id: 'task_persisted',
                status: 'compile_verified_only',
                verification_level: 'compile_verified_only',
                state: 'completed',
                last_seq: 9,
                terminal: true,
                requires_review: false,
                reason: 'persisted terminal result'
              }
            ]
          }
        : okResponse
    );
    const store = new CodingTaskStore();
    await store.refreshPersistedTasks();
    expect(store.persistedTasks).toHaveLength(1);
    expect(store.persistedTasks[0]?.task_id).toBe('task_persisted');
    expect(store.persistedTasks[0]?.status).toBe('compile_verified_only');
  });

  it('recover restores verified events but never auto-resumes a non-terminal task', async () => {
    routeByCommand((cmd) =>
      cmd === 'coding_recover_task'
        ? {
            task_id: 'task_waiting',
            status: 'paused_for_review',
            verification_level: 'none',
            state: 'waiting_host',
            terminal: false,
            requires_review: true,
            reason: 'restart requires explicit review; automatic resume is disabled',
            events: [
              {
                seq: 1,
                event_type: 'waiting_host',
                state_before: 'running',
                state_after: 'waiting_host',
                payload: {},
                event_hash: 'h1'
              }
            ]
          }
        : okResponse
    );
    const store = new CodingTaskStore();
    await store.recover('task_waiting');
    expect(store.taskId).toBe('task_waiting');
    expect(store.status).toBe('paused_for_review');
    expect(store.events).toHaveLength(1);
    expect(store.recoveryReason).toContain('automatic resume is disabled');
  });

  it('refreshEvents keeps previous events on poll miss', async () => {
    routeByCommand((cmd) => {
      if (cmd === 'coding_start_approval') return envelope;
      if (cmd === 'coding_events') throw new Error('x');
      return okResponse;
    });
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    const events = [{ seq: 1, event_type: 'e', state_before: 'A', state_after: 'B', payload: {}, event_hash: 'h' }];
    store.events = events;
    await store.refreshEvents();
    expect(store.events).toBe(events);
  });

  it('refreshEvents without a task is a no-op', async () => {
    const store = new CodingTaskStore();
    await store.refreshEvents();
    expect(invokeMocks.invoke).not.toHaveBeenCalled();
  });

  it('reset returns to idle and clears evidence', async () => {
    routeByCommand((cmd) => (cmd === 'coding_start_approval' ? envelope : okResponse));
    const store = new CodingTaskStore();
    await store.start('C:\\ws', 'a.rs', 'x');
    store.reset();
    expect(store.status).toBe('idle');
    expect(store.lastResult).toBeNull();
  });
});
