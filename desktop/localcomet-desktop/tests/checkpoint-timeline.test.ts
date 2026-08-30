import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CheckpointTimeline,
  groupByTask,
  type CheckpointRow
} from '$lib/stores/checkpointTimeline';

const row = (id: string, taskId: string, status = 'applied'): CheckpointRow => ({
  checkpoint_id: id,
  parent_checkpoint_id: null,
  patch_id: `patch_${id}`,
  task_id: taskId,
  step_id: 'step_1',
  status,
  trigger: 'patch_apply',
  paths: ['a.txt'],
  operations: ['modify'],
  before_sha256: { 'a.txt': 'aaa' },
  after_sha256: { 'a.txt': 'bbb' },
  ownership: 'user'
});

const invokeMocks = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => invokeMocks);

describe('groupByTask', () => {
  it('groups rows by task preserving order', () => {
    const groups = groupByTask([row('cp1', 't1'), row('cp2', 't2'), row('cp3', 't1')]);
    expect(groups.map((g) => g.taskId)).toEqual(['t1', 't2']);
    expect(groups[0].items.map((r) => r.checkpoint_id)).toEqual(['cp1', 'cp3']);
  });

  it('returns empty for empty rows', () => {
    expect(groupByTask([])).toEqual([]);
  });
});

describe('CheckpointTimeline state machine', () => {
  beforeEach(() => {
    invokeMocks.invoke.mockReset();
  });

  it('idle -> loading -> ready on successful list', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1')]);
    const tl = new CheckpointTimeline();
    const pending = tl.refresh();
    expect(tl.snapshot().kind).toBe('loading');
    await pending;
    const snap = tl.snapshot();
    expect(snap.kind).toBe('ready');
    expect(snap.kind === 'ready' && snap.rows.length).toBe(1);
  });

  it('list failure surfaces failed without fake ready', async () => {
    invokeMocks.invoke.mockRejectedValueOnce({ code: 'checkpoint_storage_unavailable', message: 'x' });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    expect(tl.snapshot()).toMatchObject({ kind: 'failed' });
  });

  it('compare_only returns drift report and never mutates', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockResolvedValueOnce({ checkpoint_id: 'cp1', compare: { 'a.txt': { modified: true, current_sha256: 'zzz' } } });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.compare('cp1');
    const snap = tl.snapshot();
    expect(snap.kind).toBe('compared');
    expect(snap.kind === 'compared' && snap.compare['a.txt']).toEqual({
      modified: true,
      current_sha256: 'zzz'
    });
  });

  it('restore requires explicit approval gate before backend call', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1')]);
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    expect(tl.snapshot().kind).toBe('restore_approval_required');
    expect(invokeMocks.invoke).toHaveBeenCalledTimes(1); // only the list so far
  });

  const envelope = {
    token: 'lcap_test',
    approvalId: 'apid_1',
    callId: 'cid_1'
  };

  it('restore success reports restored count from backend truth', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockResolvedValueOnce(envelope)
      .mockResolvedValueOnce({ checkpoint_id: 'cp1', restored: 1, status: 'restored', approval_consumed: true });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    await tl.confirmRestore('cp1');
    expect(tl.snapshot()).toMatchObject({ kind: 'restored', restored: 1, grantConsumed: true });
  });

  it('restore mints a one-time grant and passes approval metadata to the command', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockResolvedValueOnce(envelope)
      .mockResolvedValueOnce({ checkpoint_id: 'cp1', restored: 1, status: 'restored' });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    await tl.confirmRestore('cp1');
    // First backend call after the gate MUST be the scoped approval mint...
    expect(invokeMocks.invoke).toHaveBeenNthCalledWith(2, 'checkpoint_restore_approval', {
      request: { operation: 'restore_files', checkpointIds: ['cp1'] }
    });
    // ...and the mutating invoke must carry the issued envelope.
    expect(invokeMocks.invoke).toHaveBeenNthCalledWith(3, 'checkpoint_restore_files', {
      checkpointId: 'cp1',
      token: envelope.token,
      approvalId: envelope.approvalId,
      callId: envelope.callId
    });
  });

  it('approval-mint failure leaves restore failed without any mutation call', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockRejectedValueOnce({ code: 'checkpoint_not_found', message: 'gone' });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    await tl.confirmRestore('cp1');
    expect(tl.snapshot().kind).toBe('failed');
    expect(invokeMocks.invoke).toHaveBeenCalledTimes(2); // list + mint only
  });

  it('restore conflict maps to CONFLICT with user-edit message', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockResolvedValueOnce(envelope)
      .mockRejectedValueOnce({ code: 'restore_conflict', message: 'user changes win' });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    await tl.confirmRestore('cp1');
    const snap = tl.snapshot();
    expect(snap.kind).toBe('conflict');
    expect(snap.kind === 'conflict' && snap.message).toContain('user');
  });

  it('backend failure during restore is failed, never restored', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockResolvedValueOnce(envelope)
      .mockRejectedValueOnce({ code: 'restore_failed', message: 'io' });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    await tl.confirmRestore('cp1');
    expect(tl.snapshot().kind).toBe('failed');
  });

  it('cancel collapses in-flight gates to idle', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1')]);
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestore('cp1');
    tl.cancel();
    expect(tl.snapshot().kind).toBe('idle');
  });

  it('confirmRestore without approval gate is a no-op', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1')]);
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.confirmRestore('cp1');
    expect(invokeMocks.invoke).toHaveBeenCalledTimes(1);
    expect(tl.snapshot().kind).toBe('ready');
  });

  it('restore_task requires explicit approval gate before backend call', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1'), row('cp2', 't1')]);
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestoreTask('t1', ['cp1', 'cp2']);
    expect(tl.snapshot().kind).toBe('restore_task_approval_required');
    expect(invokeMocks.invoke).toHaveBeenCalledTimes(1); // only the list so far
  });

  it('restore_task success reports backend truth and passes ids plus grant to the command', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1'), row('cp2', 't1')])
      .mockResolvedValueOnce(envelope)
      .mockResolvedValueOnce({
        task_id: 't1',
        restored: 2,
        checkpoints: 2,
        status: 'restored_task',
        approval_consumed: true
      });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestoreTask('t1', ['cp1', 'cp2']);
    await tl.confirmRestoreTask();
    expect(tl.snapshot()).toMatchObject({
      kind: 'restored_task',
      restored: 2,
      checkpoints: 2,
      grantConsumed: true
    });
    expect(invokeMocks.invoke).toHaveBeenNthCalledWith(2, 'checkpoint_restore_approval', {
      request: { operation: 'restore_task', checkpointIds: ['cp1', 'cp2'] }
    });
    expect(invokeMocks.invoke).toHaveBeenNthCalledWith(3, 'checkpoint_restore_task', {
      checkpointIds: ['cp1', 'cp2'],
      token: envelope.token,
      approvalId: envelope.approvalId,
      callId: envelope.callId
    });
  });

  it('restore_task conflict maps to a typed task-conflict state', async () => {
    invokeMocks.invoke
      .mockResolvedValueOnce([row('cp1', 't1')])
      .mockResolvedValueOnce(envelope)
      .mockRejectedValueOnce({
        code: 'restore_conflict',
        message: 'restore_conflict@cp_abc:restore_conflict'
      });
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestoreTask('t1', ['cp1']);
    await tl.confirmRestoreTask();
    const snap = tl.snapshot();
    expect(snap.kind).toBe('restore_task_conflict');
    expect(snap.kind === 'restore_task_conflict' && snap.taskId).toBe('t1');
  });

  it('restore_task cancel collapses the approval gate to idle', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1')]);
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.requestRestoreTask('t1', ['cp1']);
    tl.cancel();
    expect(tl.snapshot().kind).toBe('idle');
  });

  it('confirmRestoreTask without gate is a no-op', async () => {
    invokeMocks.invoke.mockResolvedValueOnce([row('cp1', 't1')]);
    const tl = new CheckpointTimeline();
    await tl.refresh();
    await tl.confirmRestoreTask();
    expect(invokeMocks.invoke).toHaveBeenCalledTimes(1);
    expect(tl.snapshot().kind).toBe('ready');
  });
});
