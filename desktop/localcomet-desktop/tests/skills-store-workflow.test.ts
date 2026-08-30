import { beforeEach, describe, expect, it, vi } from 'vitest';

const approvalMocks = vi.hoisted(() => ({
  requestApproval: vi.fn(),
  runToolCall: vi.fn(),
}));

const invokeMocks = vi.hoisted(() => ({
  invoke: vi.fn(),
}));

vi.mock('$lib/bridge/approval', () => approvalMocks);
vi.mock('@tauri-apps/api/core', () => invokeMocks);

import { skillsStore } from '$lib/stores/skillsStore';

const verifiedResult = (overrides: Record<string, unknown> = {}) => ({
  tool: 'computer_use',
  schema_version: 'computer_use.result.v1',
  status: 'completed',
  terminal: true,
  succeeded: true,
  verification: 'verified',
  ...overrides,
});

const workflowPlan = {
  steps: [
    {
      id: 'open_notepad',
      action: 'computer_use.open_app',
      requires_approval: true,
      arguments: { target: 'notepad' },
      precondition: { kind: 'owned_session_ready' },
      postcondition: { kind: 'owned_process_window', app: 'notepad' },
    },
    {
      id: 'wait_notepad',
      action: 'computer_use.wait_for_window',
      requires_approval: false,
      arguments: { target: 'notepad', seconds: 1 },
      precondition: { kind: 'launch_pending', step: 'open_notepad' },
      postcondition: { kind: 'wait_complete', app: 'notepad' },
    },
    {
      id: 'observe_document',
      action: 'computer_use.observe',
      requires_approval: false,
      arguments: { target: 'notepad', fresh: true },
      precondition: { kind: 'window_ready', step: 'wait_notepad' },
      postcondition: { kind: 'fresh_uia_observation', control_type: 'DocumentControl' },
    },
    {
      id: 'type_marker',
      action: 'computer_use.type_element',
      requires_approval: true,
      arguments: { target: 'Document', text: 'TEST_MARKER' },
      precondition: { kind: 'fresh_uia_observation', step: 'observe_document' },
      postcondition: { kind: 'fresh_uia_text_contains', text: 'TEST_MARKER' },
    },
    {
      id: 'close_owned_notepad',
      action: 'computer_use.close_owned',
      requires_approval: true,
      arguments: { ownership: 'broker_owned_only', app: 'notepad' },
      precondition: { kind: 'owned_process_started', step: 'open_notepad' },
      postcondition: { kind: 'owned_process_terminated', app: 'notepad' },
    },
  ],
};

function configureCompile() {
  invokeMocks.invoke.mockResolvedValue({ success: true, result: workflowPlan });
  approvalMocks.requestApproval.mockImplementation(async (tool: string, input: unknown) => ({
    token: 'approval-token',
    approvalId: `approval-${approvalMocks.requestApproval.mock.calls.length}`,
    callId: `call-${approvalMocks.requestApproval.mock.calls.length}`,
    tool,
    input,
  }));
}

describe('skillsStore declarative workflow runner', () => {
  beforeEach(() => {
    invokeMocks.invoke.mockReset();
    approvalMocks.requestApproval.mockReset();
    approvalMocks.runToolCall.mockReset();
    configureCompile();
  });

  it('runs the bounded open -> wait -> observe -> type -> close lifecycle with scoped approvals', async () => {
    approvalMocks.runToolCall
      .mockResolvedValueOnce(verifiedResult({
        status: 'launch_pending',
        succeeded: false,
        verification: 'not_applicable',
        execution: { mode: 'cu_broker_spawn' },
      }))
      .mockResolvedValueOnce(verifiedResult({ verification: 'not_applicable' }))
      .mockResolvedValueOnce(verifiedResult())
      .mockResolvedValueOnce(verifiedResult())
      .mockResolvedValueOnce(verifiedResult());

    const result = await skillsStore.runSkillWorkflow('notepad-bounded-note', { text: 'TEST_MARKER' });

    expect(result.success).toBe(true);
    expect(result.results).toHaveLength(5);
    expect(approvalMocks.requestApproval.mock.calls.map((call: any[]) => [call[0], (call[1] as { action: string }).action])).toEqual([
      ['skills.invoke', 'compile'],
      ['computer_use', 'open_app'],
      ['computer_use', 'type_element'],
      ['computer_use', 'close_owned'],
    ]);

    const calls = approvalMocks.runToolCall.mock.calls;
    expect(calls).toHaveLength(5);
    expect(calls[1][2]).toBeUndefined();
    expect(calls[2][2]).toBeUndefined();
    expect(calls[0][4]).toMatch(/^[0-9a-f]{24}$/);
    expect(new Set(calls.map((call) => call[4])).size).toBe(5);
    expect((calls[4][1] as Record<string, unknown>).ownership_request_id).toBe(calls[0][4]);
    expect(calls[4][5]).toContain('skill_notepad-bounded-note_close_owned_notepad_4');
  });

  it('does not allow a launch_pending open to become success before observe and closes the owned launch on observation failure', async () => {
    approvalMocks.runToolCall
      .mockResolvedValueOnce(verifiedResult({
        status: 'launch_pending',
        succeeded: false,
        verification: 'not_applicable',
        execution: { mode: 'cu_broker_spawn' },
      }))
      .mockResolvedValueOnce(verifiedResult({ verification: 'not_applicable' }))
      .mockResolvedValueOnce(verifiedResult({ succeeded: false, verification: 'not_verified' }))
      .mockResolvedValueOnce(verifiedResult());

    const result = await skillsStore.runSkillWorkflow('notepad-bounded-note', { text: 'TEST_MARKER' });

    expect(result.success).toBe(false);
    expect(result.results.map((item: { action: string }) => item.action)).toEqual([
      'open_app',
      'wait_for_window',
      'observe',
      'close_owned',
    ]);
    expect(approvalMocks.runToolCall).toHaveBeenCalledTimes(4);
    expect((approvalMocks.runToolCall.mock.calls[3][1] as Record<string, unknown>).ownership_request_id)
      .toBe(approvalMocks.runToolCall.mock.calls[0][4]);
    expect(approvalMocks.requestApproval.mock.calls.map((call: any[]) => (call[1] as { action: string }).action)).toEqual([
      'compile',
      'open_app',
      'close_owned',
    ]);
  });

  it('attempts declared cleanup when a mutating step throws after an owned launch', async () => {
    approvalMocks.runToolCall
      .mockResolvedValueOnce(verifiedResult({
        status: 'launch_pending',
        succeeded: false,
        verification: 'not_applicable',
        execution: { mode: 'cu_broker_spawn' },
      }))
      .mockResolvedValueOnce(verifiedResult({ verification: 'not_applicable' }))
      .mockResolvedValueOnce(verifiedResult())
      .mockRejectedValueOnce({ code: 'path_outside_workspace', message: 'private path detail must not escape' })
      .mockResolvedValueOnce(verifiedResult());

    const result = await skillsStore.runSkillWorkflow('notepad-bounded-note', { text: 'TEST_MARKER' });

    expect(result.success).toBe(false);
    expect(result.results.at(-1)).toMatchObject({ action: 'close_owned', cleanup: true });
    expect(approvalMocks.runToolCall).toHaveBeenCalledTimes(5);
    expect((approvalMocks.runToolCall.mock.calls.at(-1)?.[1] as Record<string, unknown>).ownership_request_id)
      .toBe(approvalMocks.runToolCall.mock.calls[0][4]);
    expect(approvalMocks.requestApproval.mock.calls.map((call: any[]) => (call[1] as { action: string }).action)).toEqual([
      'compile',
      'open_app',
      'type_element',
      'close_owned',
    ]);
  });
});

export {};
