import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn()
}));

import { invoke } from '@tauri-apps/api/core';
import {
  approvalStore,
  confirmApproval,
  hasPendingApproval,
  rejectApproval,
  requestApprovalForTool,
  resetApprovalStore
} from '../src/lib/stores/approvalStore';

const mockedInvoke = vi.mocked(invoke);
const TOKEN = 'lcap_' + 'a'.repeat(64);

function envelopeFor(tool: string) {
  return { token: TOKEN, approvalId: 'appr_' + 'b'.repeat(32), callId: 'call_' + 'c'.repeat(32), tool, riskLevel: 'guarded', commandFamily: 'artifact_download', expiresAtUnixMs: Date.now() + 300_000 };
}

describe('approvalStore', () => {
  beforeEach(() => {
    resetApprovalStore();
    mockedInvoke.mockReset();
  });

  it('starts idle with no pending approval', () => {
    expect(get(approvalStore).phase).toBe('idle');
    expect(get(hasPendingApproval)).toBe(false);
  });

  it('requestApprovalForTool sets a pending approval', () => {
    requestApprovalForTool('files.write', { path: 'a.txt', content: 'x' });
    const state = get(approvalStore);
    expect(state.pending).toEqual({ tool: 'files.write', input: { path: 'a.txt', content: 'x' }, envelope: null });
    expect(state.phase).toBe('pending');
    expect(get(hasPendingApproval)).toBe(true);
  });

  it('rejectApproval clears the pending approval', () => {
    requestApprovalForTool('files.write', {});
    rejectApproval();
    expect(get(approvalStore).pending).toBeNull();
    expect(get(approvalStore).phase).toBe('idle');
  });

  it('confirmApproval requests approval then runs the tool and resets on success', async () => {
    requestApprovalForTool('files.write', { path: 'a.txt' });
    mockedInvoke.mockImplementation(async (command: string, args?: unknown) => {
      if (command === 'request_approval') return envelopeFor((args as { tool: string }).tool);
      if (command === 'run_tool_call') return { tool: 'files.write', path: '/w/a.txt' };
      throw new Error('unexpected command ' + command);
    });
    await confirmApproval();
    const commands = mockedInvoke.mock.calls.map((call) => call[0]);
    expect(commands).toEqual(['request_approval', 'run_tool_call']);
    expect(mockedInvoke).toHaveBeenLastCalledWith('run_tool_call', {
      tool: 'files.write',
      input: { path: 'a.txt' },
      token: TOKEN,
      approvalId: 'appr_' + 'b'.repeat(32),
      callId: 'call_' + 'c'.repeat(32)
    });
    expect(get(approvalStore).phase).toBe('idle');
    expect(get(approvalStore).pending).toBeNull();
  });

  it('confirmApproval records grant_expired for re-approval (ADR-013 R6)', async () => {
    requestApprovalForTool('files.delete', { path: 'a.txt' });
    mockedInvoke.mockImplementation(async (command: string, args?: unknown) => {
      if (command === 'request_approval') return envelopeFor((args as { tool: string }).tool);
      throw { code: 'grant_expired', message: 'execution grant expired' };
    });
    await confirmApproval();
    const state = get(approvalStore);
    expect(state.phase).toBe('error');
    expect(state.errorCode).toBe('grant_expired');
    expect(state.pending).not.toBeNull();
  });

  it('confirmApproval maps a policy_blocked error code', async () => {
    requestApprovalForTool('files.write', { path: '../escape.txt' });
    mockedInvoke.mockImplementation(async (command: string, args?: unknown) => {
      if (command === 'request_approval') return envelopeFor((args as { tool: string }).tool);
      throw { code: 'policy_blocked', message: 'outside workspace' };
    });
    await confirmApproval();
    expect(get(approvalStore).errorCode).toBe('policy_blocked');
  });

  it('confirmApproval without a pending approval is a no-op', async () => {
    await confirmApproval();
    expect(mockedInvoke).not.toHaveBeenCalled();
    expect(get(approvalStore).phase).toBe('idle');
  });
});
