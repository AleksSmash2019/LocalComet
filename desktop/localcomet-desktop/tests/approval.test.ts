import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn()
}));

import { invoke } from '@tauri-apps/api/core';
import {
  approvalPrompt,
  approvalPromptActive,
  approvalStore,
  confirmApproval,
  hasPendingApproval,
  rejectApproval,
  requestApprovalForTool,
  rejectActiveApproval,
  resetApprovalStore,
  setApprovalCorrelation,
  setApprovalPrompt,
  normalizeApprovalPrompt
} from '../src/lib/stores/approvalStore';

const mockedInvoke = vi.mocked(invoke);
const TOKEN = 'lcap_' + 'a'.repeat(64);

function envelopeFor(tool: string) {
  const isComputerUse = tool === 'computer_use';
  const isFilesystemDelete = tool === 'files.delete';
  return {
    token: TOKEN,
    approvalId: 'appr_' + 'b'.repeat(32),
    callId: 'call_' + 'c'.repeat(32),
    tool,
    riskLevel: isComputerUse || isFilesystemDelete ? 'dangerous' : 'guarded',
    commandFamily: isComputerUse ? 'computer_use' : isFilesystemDelete ? 'tool_filesystem_delete' : 'artifact_download',
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
        callId: 'call_' + 'c'.repeat(32),
        requestId: null,
        actionId: null
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

  it('rejects malformed approval events before they reach the prompt store', () => {
    const valid = {
      request_id: 'appr_' + 'd'.repeat(32),
      tool: 'computer_use',
      risk_level: 'dangerous',
      target_summary: '{}',
      side_effect_category: 'computer_control',
      destructive: true,
      input_digest: 'd'.repeat(64)
    };
    expect(setApprovalPrompt(valid)).toBe(true);
    expect(setApprovalPrompt({ ...valid, input_digest: '' })).toBe(false);
    expect(get(approvalPrompt)).toBeNull();
    expect(get(approvalPromptActive)).toBe(false);
    expect(normalizeApprovalPrompt({ ...valid, request_id: 'appr_' + 'D'.repeat(32) })).toBeNull();
    expect(normalizeApprovalPrompt({ ...valid, model_action_id: 'call_\u0000bad' })).toBeNull();
  });

  it('rejects partial correlation and never inherits stale UI identity', () => {
    const base = {
      request_id: 'appr_' + 'f'.repeat(32),
      tool: 'computer_use',
      risk_level: 'dangerous',
      target_summary: '{}',
      side_effect_category: 'computer_control',
      destructive: true,
      input_digest: 'f'.repeat(64)
    };
    setApprovalCorrelation({
      modelRequestId: '0123456789abcdef01234567',
      modelActionId: 'call_0123456789abcdef0123456789ab'
    });
    expect(normalizeApprovalPrompt({ ...base, model_request_id: '0123456789abcdef01234567' })).toBeNull();
    expect(setApprovalPrompt(base)).toBe(true);
    expect(get(approvalPrompt)).toEqual(expect.objectContaining(base));
    expect(get(approvalPrompt)).not.toHaveProperty('model_request_id');
    expect(get(approvalPrompt)).not.toHaveProperty('model_action_id');
  });

  it('normalizes only bounded optional correlation metadata', () => {
    const prompt = normalizeApprovalPrompt({
      request_id: 'appr_' + 'd'.repeat(32),
      model_request_id: '0123456789abcdef01234567',
      model_action_id: 'call_0123456789abcdef0123456789ab',
      tool: 'computer_use',
      risk_level: 'dangerous',
      target_summary: '{"action":"open_app"}',
      side_effect_category: 'computer_control',
      destructive: true,
      input_digest: 'd'.repeat(64),
      expires_at_unix_ms: Date.now() + 120_000,
      ignored: 'not rendered'
    });
    expect(prompt).toEqual(expect.objectContaining({
      model_request_id: '0123456789abcdef01234567',
      model_action_id: 'call_0123456789abcdef0123456789ab',
      input_digest: 'd'.repeat(64)
    }));
    expect(prompt).not.toHaveProperty('ignored');
    expect(normalizeApprovalPrompt({
      request_id: 'appr_' + 'd'.repeat(32),
      model_request_id: 'bad',
      tool: 'computer_use',
      risk_level: 'dangerous',
      target_summary: '{}',
      side_effect_category: 'computer_control',
      destructive: true,
      input_digest: 'd'.repeat(64)
    })).toBeNull();
  });

  it('rejects an active frontend prompt and clears its shared state', async () => {
    setApprovalPrompt({
      request_id: 'appr_' + 'd'.repeat(32),
      tool: 'computer_use',
      risk_level: 'dangerous',
      target_summary: '{"action":"open_app","target":"calculator"}',
      side_effect_category: 'computer_control',
      destructive: true,
      input_digest: 'd'.repeat(64),
      expires_at_unix_ms: Date.now() + 120_000
    });
    mockedInvoke.mockResolvedValue(undefined);

    await rejectActiveApproval();

    expect(mockedInvoke).toHaveBeenCalledWith('resolve_tool_approval', {
      requestId: 'appr_' + 'd'.repeat(32),
      decision: 'reject'
    });
    expect(get(approvalPrompt)).toBeNull();
    expect(get(approvalPromptActive)).toBe(false);
  });

  it('does not execute a dangerous tool until the approval decision resolves', async () => {
    const onResult = vi.fn();
    let resolveRequest: ((value: unknown) => void) | undefined;
    mockedInvoke.mockImplementation(async (command: string) => {
      if (command === 'request_approval') {
        return new Promise<unknown>((resolve) => {
          resolveRequest = resolve;
        });
      }
      if (command === 'run_tool_call') return { tool: 'computer_use' };
      throw new Error('unexpected command ' + command);
    });

    requestApprovalForTool('computer_use', { action: 'screenshot' }, { onResult });
    await flushBackgroundApproval();
    await flushBackgroundApproval();

    expect(get(approvalStore).phase).toBe('requesting');
    expect(mockedInvoke.mock.calls.filter((call) => call[0] === 'run_tool_call')).toHaveLength(0);

    resolveRequest?.(envelopeFor('computer_use'));
    await flushBackgroundApproval();
    await flushBackgroundApproval();

    expect(mockedInvoke.mock.calls.map((call) => call[0])).toEqual([
      'request_approval',
      'run_tool_call'
    ]);
    expect(onResult).toHaveBeenCalledWith({ tool: 'computer_use' });
    expect(get(approvalStore).phase).toBe('idle');
  });
});


// P0.2: model-turn correlation is transport metadata, never part of tool input.
describe('approval correlation boundary', () => {
  beforeEach(() => {
    resetApprovalStore();
    mockedInvoke.mockReset();
  });

  it('passes requestId/actionId out-of-band and preserves raw computer_use input', async () => {
    const input = { action: 'open_app', target: 'notepad' };
    const requestId = '0123456789abcdef01234567';
    const actionId = 'call_0123456789abcdef0123456789ab';
    const onResult = vi.fn();
    mockedInvoke.mockImplementation(async (command: string, args?: unknown) => {
      if (command === 'request_approval') return envelopeFor('computer_use');
      if (command === 'run_tool_call') return { tool: 'computer_use', status: 'completed' };
      throw new Error('unexpected command ' + command);
    });

    requestApprovalForTool('computer_use', input, { onResult, requestId, actionId });
    await flushBackgroundApproval();

    expect(mockedInvoke.mock.calls[0]).toEqual([
      'request_approval',
      { tool: 'computer_use', input, requestId, actionId }
    ]);
    expect(mockedInvoke.mock.calls[1]).toEqual([
      'run_tool_call',
      expect.objectContaining({
        tool: 'computer_use',
        input,
        requestId,
        actionId
      })
    ]);
    expect((mockedInvoke.mock.calls[1][1] as Record<string, unknown>).input).toEqual(input);
    expect((mockedInvoke.mock.calls[1][1] as Record<string, unknown>).input).not.toHaveProperty('request_id');
    expect((mockedInvoke.mock.calls[1][1] as Record<string, unknown>).input).not.toHaveProperty('action_id');
    expect(onResult).toHaveBeenCalledWith({ tool: 'computer_use', status: 'completed' });
  });

  it('uses server correlation over stale pending UI correlation', () => {
    setApprovalCorrelation({
      modelRequestId: '0123456789abcdef01234567',
      modelActionId: 'call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    });
    setApprovalPrompt({
      request_id: 'appr_' + 'e'.repeat(32),
      model_request_id: '0123456789abcdef01234567',
      model_action_id: 'call_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      tool: 'computer_use',
      risk_level: 'dangerous',
      target_summary: '{"action":"open_app","target":"notepad"}',
      side_effect_category: 'computer_control',
      destructive: true,
      input_digest: 'e'.repeat(64),
      expires_at_unix_ms: Date.now() + 120_000
    });

    expect(get(approvalPrompt)?.model_action_id).toBe('call_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb');
  });
});
