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
  return {
    token: TOKEN,
    approvalId: 'appr_' + 'b'.repeat(32),
    callId: 'call_' + 'c'.repeat(32),
    tool,
    riskLevel: 'guarded',
    commandFamily: 'artifact_download',
    expiresAtUnixMs: Date.now() + 300_000
  };
}

async function flushBackgroundApproval(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
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

  it('starts guarded tool execution in the background without a pending card', async () => {
    const onResult = vi.fn();
    mockedInvoke.mockImplementation(async (command: string, args?: unknown) => {
      if (command === 'request_approval') return envelopeFor((args as { tool: string }).tool);
      if (command === 'run_tool_call') return { tool: 'files.write', path: '/w/a.txt' };
      throw new Error('unexpected command ' + command);
    });

    requestApprovalForTool('files.write', { path: 'a.txt' }, { onResult });
    expect(get(approvalStore).pending).toBeNull();
    expect(get(hasPendingApproval)).toBe(false);
    await flushBackgroundApproval();

    expect(mockedInvoke.mock.calls.map((call) => call[0])).toEqual([
      'request_approval',
      'run_tool_call'
    ]);
    expect(onResult).toHaveBeenCalledWith({ tool: 'files.write', path: '/w/a.txt' });
    expect(get(approvalStore).phase).toBe('idle');
    expect(get(approvalStore).pending).toBeNull();
  });

  it('runs the Rust approval boundary without opening a user-facing card', async () => {
    mockedInvoke.mockImplementation(async (command: string, args?: unknown) => {
      if (command === 'request_approval') return envelopeFor((args as { tool: string }).tool);
      if (command === 'run_tool_call') return { tool: 'files.delete', ok: true };
      throw new Error('unexpected command ' + command);
    });

    requestApprovalForTool('files.delete', { path: 'a.txt' });
    await flushBackgroundApproval();

    expect(mockedInvoke.mock.calls[1]).toEqual([
      'run_tool_call',
      {
        tool: 'files.delete',
        input: { path: 'a.txt' },
        token: TOKEN,
        approvalId: 'appr_' + 'b'.repeat(32),
        callId: 'call_' + 'c'.repeat(32)
      }
    ]);
    expect(get(hasPendingApproval)).toBe(false);
  });

  it('reports background execution errors without rendering a pending card', async () => {
    const onError = vi.fn();
    mockedInvoke.mockImplementation(async (command: string) => {
      if (command === 'request_approval') return envelopeFor('files.write');
      throw { code: 'policy_blocked', message: 'outside workspace' };
    });

    requestApprovalForTool('files.write', { path: '../escape.txt' }, { onError });
    await flushBackgroundApproval();

    expect(onError).toHaveBeenCalledWith({ code: 'policy_blocked', message: 'outside workspace' });
    expect(get(approvalStore).pending).toBeNull();
    expect(get(approvalStore).phase).toBe('error');
    expect(get(approvalStore).errorCode).toBe('policy_blocked');
    expect(get(hasPendingApproval)).toBe(false);
  });

  it('rejectApproval remains a compatibility no-op when no card exists', () => {
    rejectApproval();
    expect(get(approvalStore).pending).toBeNull();
    expect(get(approvalStore).phase).toBe('idle');
  });

  it('confirmApproval without a pending approval is a no-op', async () => {
    await confirmApproval();
    expect(mockedInvoke).not.toHaveBeenCalled();
    expect(get(approvalStore).phase).toBe('idle');
  });
});
