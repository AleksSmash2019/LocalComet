import { beforeEach, describe, expect, it, vi } from 'vitest';
import { validateApprovalEnvelope } from '../src/lib/bridge/approval';
import type { ApprovalEnvelope } from '../src/lib/bridge/approval';
import fixture from '../../../security/contracts/approval_envelope_v1.fixture.json';

const sharedFixture = fixture as unknown as ApprovalEnvelope;

function validEnvelope(tool = 'artifact.download'): ApprovalEnvelope {
  return { ...sharedFixture, tool, expiresAtUnixMs: Date.now() + 300_000 };
}

let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let approvalResponse: unknown = validEnvelope();
let protectedResponse: unknown = {};

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    invokeCalls.push({ command, args });
    if (command === 'request_approval') {
      if (approvalResponse instanceof Error) throw approvalResponse;
      return approvalResponse;
    }
    return protectedResponse;
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (): Promise<() => void> => () => undefined)
}));

describe('p0b-r5-approval-contract', () => {
  beforeEach(() => {
    invokeCalls = [];
    approvalResponse = validEnvelope();
    protectedResponse = {};
  });

  it('p0b_r5_frontend_accepts_shared_fixture', () => {
    const envelope = validateApprovalEnvelope({ ...sharedFixture, expiresAtUnixMs: Date.now() + 300_000 }, 'artifact.download');
    expect(envelope.token).toBe(sharedFixture.token);
    expect(envelope.approvalId).toBe(sharedFixture.approvalId);
    expect(envelope.callId).toBe(sharedFixture.callId);
    expect(envelope.tool).toBe('artifact.download');
    expect(envelope.riskLevel).toBe('guarded');
    expect(envelope.commandFamily).toBe('artifact_download');
  });

  it('p0b_r5_frontend_rejects_plain_token_string', () => {
    expect(() => validateApprovalEnvelope(sharedFixture.token, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_null', () => {
    expect(() => validateApprovalEnvelope(null, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_array', () => {
    expect(() => validateApprovalEnvelope([validEnvelope()], 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_missing_approval_id', () => {
    const { approvalId: _, ...rest } = validEnvelope();
    expect(() => validateApprovalEnvelope(rest, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_missing_call_id', () => {
    const { callId: _, ...rest } = validEnvelope();
    expect(() => validateApprovalEnvelope(rest, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_missing_risk', () => {
    const { riskLevel: _, ...rest } = validEnvelope();
    expect(() => validateApprovalEnvelope(rest, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_missing_family', () => {
    const { commandFamily: _, ...rest } = validEnvelope();
    expect(() => validateApprovalEnvelope(rest, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_invalid_expiry', () => {
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), expiresAtUnixMs: NaN }, 'artifact.download')).toThrow();
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), expiresAtUnixMs: -1 }, 'artifact.download')).toThrow();
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), expiresAtUnixMs: 'soon' }, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_expired_envelope', () => {
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), expiresAtUnixMs: Date.now() - 1000 }, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_wrong_tool', () => {
    expect(() => validateApprovalEnvelope(validEnvelope('artifact.download'), 'artifact.remove')).toThrow();
  });

  it('p0b_r5_frontend_rejects_invalid_token', () => {
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), token: 'bad_token' }, 'artifact.download')).toThrow();
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), token: `lcap_${'g'.repeat(64)}` }, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_invalid_approval_id', () => {
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), approvalId: 'bad_id' }, 'artifact.download')).toThrow();
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), approvalId: `appr_${'z'.repeat(32)}` }, 'artifact.download')).toThrow();
  });

  it('p0b_r5_frontend_rejects_invalid_call_id', () => {
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), callId: 'bad_id' }, 'artifact.download')).toThrow();
    expect(() => validateApprovalEnvelope({ ...validEnvelope(), callId: `call_${'z'.repeat(32)}` }, 'artifact.download')).toThrow();
  });

  it('p0b_r5_download_passes_all_three_identifiers', async () => {
    const { startApprovedArtifactDownload } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };
    await startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap');
    const protectedCall = invokeCalls.find((c) => c.command === 'start_approved_artifact_download');
    expect(protectedCall?.args?.token).toBe(sharedFixture.token);
    expect(protectedCall?.args?.approvalId).toBe(sharedFixture.approvalId);
    expect(protectedCall?.args?.callId).toBe(sharedFixture.callId);
    expect(protectedCall?.args).not.toHaveProperty('customUrl');
  });

  it('p0b_r5_custom_download_binds_exact_url_to_approval_and_execution', async () => {
    const { startArbitraryHuggingFaceDownload } = await import('../src/lib/bridge/modelGateway');
    const customUrl = 'https://huggingface.co/owner/repo/resolve/main/model.gguf';
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'custom-owner-repo-model-1234567890ab', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };

    await startArbitraryHuggingFaceDownload(customUrl);

    expect(invokeCalls).toEqual([
      { command: 'request_approval', args: { tool: 'artifact.download', input: { custom_url: customUrl } } },
      {
        command: 'start_approved_artifact_download',
        args: {
          customUrl,
          token: sharedFixture.token,
          approvalId: sharedFixture.approvalId,
          callId: sharedFixture.callId
        }
      }
    ]);
  });

  it('p0b_r5_remove_passes_all_three_identifiers', async () => {
    const { removeManagedModel } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.remove');
    protectedResponse = { model_id: 'qwen2.5-1.5b-instruct-q4-k-m', removed: true };
    await removeManagedModel('qwen2.5-1.5b-instruct-q4-k-m');
    const protectedCall = invokeCalls.find((c) => c.command === 'remove_managed_model');
    expect(protectedCall?.args?.token).toBe(sharedFixture.token);
    expect(protectedCall?.args?.approvalId).toBe(sharedFixture.approvalId);
    expect(protectedCall?.args?.callId).toBe(sharedFixture.callId);
  });

  it('p0b_r5_runtime_start_passes_all_three_identifiers', async () => {
    const { startManagedRuntime } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('runtime.start');
    protectedResponse = {
      state: 'Ready', model_state: 'Ready', inference_ready: true, provider_id: 'managed-llama-cpp',
      model_id: 'qwen2.5-1.5b-instruct-q4-k-m', model_display_name: 'Test', runtime_instance_id: 'd'.repeat(32), runtime_instance_fingerprint: 'e'.repeat(64)
    };
    await startManagedRuntime('qwen2.5-1.5b-instruct-q4-k-m');
    const protectedCall = invokeCalls.find((c) => c.command === 'managed_runtime_start');
    expect(protectedCall?.args?.token).toBe(sharedFixture.token);
    expect(protectedCall?.args?.approvalId).toBe(sharedFixture.approvalId);
    expect(protectedCall?.args?.callId).toBe(sharedFixture.callId);
    expect(protectedCall?.args).not.toHaveProperty('customSha256');
    expect((invokeCalls.find((c) => c.command === 'request_approval')?.args?.input as Record<string, unknown>)).not.toHaveProperty('custom_sha256');
  });

  it('p0b_r5_custom_runtime_start_binds_digest_to_approval_and_execution', async () => {
    const { startManagedRuntime } = await import('../src/lib/bridge/modelGateway');
    const modelId = 'custom-owner-repo-model-1234567890ab';
    const customSha256 = 'e'.repeat(64);
    approvalResponse = validEnvelope('runtime.start');
    protectedResponse = {
      state: 'Ready', model_state: 'Ready', inference_ready: true, provider_id: 'managed-llama-cpp',
      model_id: modelId, model_display_name: 'Custom model', runtime_instance_id: 'd'.repeat(32), runtime_instance_fingerprint: 'e'.repeat(64)
    };

    await startManagedRuntime(modelId, customSha256);

    expect(invokeCalls).toEqual([
      { command: 'request_approval', args: { tool: 'runtime.start', input: { model_id: modelId, custom_sha256: customSha256 } } },
      {
        command: 'managed_runtime_start',
        args: {
          modelId,
          customSha256,
          token: sharedFixture.token,
          approvalId: sharedFixture.approvalId,
          callId: sharedFixture.callId
        }
      }
    ]);
  });

  it('p0b_r5_runtime_start_refuses_stale_selection_after_approval', async () => {
    const { startManagedRuntime } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('runtime.start');
    await expect(startManagedRuntime('qwen2.5-1.5b-instruct-q4-k-m', () => false)).rejects.toMatchObject({
      code: 'stale_request'
    });
    expect(invokeCalls.map((call) => call.command)).toEqual(['request_approval']);
  });

  it('p0b_r5_runtime_stop_passes_all_three_identifiers', async () => {
    const { stopManagedRuntime } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('runtime.stop');
    protectedResponse = {};
    await stopManagedRuntime();
    const protectedCall = invokeCalls.find((c) => c.command === 'managed_runtime_stop');
    expect(protectedCall?.args?.token).toBe(sharedFixture.token);
    expect(protectedCall?.args?.approvalId).toBe(sharedFixture.approvalId);
    expect(protectedCall?.args?.callId).toBe(sharedFixture.callId);
  });

  it('p0b_r5_model_binding_passes_all_three_identifiers', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('model.binding.set');
    protectedResponse = {
      provider_id: 'managed-llama-cpp', harness_id: 'minimal', model_id: 'qwen2.5-1.5b-instruct-q4-k-m',
      binding_fingerprint: 'f'.repeat(64), discovered_fingerprint: '9'.repeat(64), persistence: false, runtime_instance_id: 'd'.repeat(32)
    };
    await setModelBinding({ providerId: 'managed-llama-cpp', harnessId: 'minimal', modelId: 'qwen2.5-1.5b-instruct-q4-k-m', runtimeInstanceId: 'd'.repeat(32) });
    const protectedCall = invokeCalls.find((c) => c.command === 'model_binding_set');
    expect(protectedCall?.args?.token).toBe(sharedFixture.token);
    expect(protectedCall?.args?.approvalId).toBe(sharedFixture.approvalId);
    expect(protectedCall?.args?.callId).toBe(sharedFixture.callId);
  });

  it('p0b_r5_frontend_sends_no_user_decision', async () => {
    const { startApprovedArtifactDownload } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };
    await startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap');
    const serialized = JSON.stringify(invokeCalls);
    expect(serialized).not.toContain('userDecision');
    expect(serialized).not.toContain('confirmed');
  });

  it('p0b_r5_rejected_approval_prevents_protected_invoke', async () => {
    const { startApprovedArtifactDownload } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = { code: 'approval_rejected', message: 'User rejected' };
    await expect(startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap')).rejects.toBeTruthy();
    expect(invokeCalls.filter((c) => c.command === 'start_approved_artifact_download')).toHaveLength(0);
  });

  it('p0b_r5_prompt_failure_prevents_protected_invoke', async () => {
    const { removeManagedModel } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = new Error('prompt dismissed');
    await expect(removeManagedModel('qwen2.5-1.5b-instruct-q4-k-m')).rejects.toBeTruthy();
    expect(invokeCalls.filter((c) => c.command === 'remove_managed_model')).toHaveLength(0);
  });

  it('p0b_r5_frontend_never_invokes_run_tool_call', async () => {
    const { startApprovedArtifactDownload, removeManagedModel, startManagedRuntime, stopManagedRuntime, setModelBinding } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };
    await startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap');
    approvalResponse = validEnvelope('artifact.remove');
    protectedResponse = { model_id: 'qwen2.5-1.5b-instruct-q4-k-m', removed: true };
    await removeManagedModel('qwen2.5-1.5b-instruct-q4-k-m');
    approvalResponse = validEnvelope('runtime.start');
    protectedResponse = {
      state: 'Ready', model_state: 'Ready', inference_ready: true, provider_id: 'managed-llama-cpp',
      model_id: 'qwen2.5-1.5b-instruct-q4-k-m', model_display_name: 'Test', runtime_instance_id: 'd'.repeat(32), runtime_instance_fingerprint: 'e'.repeat(64)
    };
    await startManagedRuntime('qwen2.5-1.5b-instruct-q4-k-m');
    approvalResponse = validEnvelope('runtime.stop');
    protectedResponse = {};
    await stopManagedRuntime();
    approvalResponse = validEnvelope('model.binding.set');
    protectedResponse = {
      provider_id: 'managed-llama-cpp', harness_id: 'minimal', model_id: 'qwen2.5-1.5b-instruct-q4-k-m',
      binding_fingerprint: 'f'.repeat(64), discovered_fingerprint: '9'.repeat(64), persistence: false, runtime_instance_id: 'd'.repeat(32)
    };
    await setModelBinding({ providerId: 'managed-llama-cpp', harnessId: 'minimal', modelId: 'qwen2.5-1.5b-instruct-q4-k-m', runtimeInstanceId: 'd'.repeat(32) });
    expect(invokeCalls.map((c) => c.command)).not.toContain('run_tool_call');
  });

  it('p0b_r5_frontend_never_invokes_set_workspace', async () => {
    const { startApprovedArtifactDownload } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };
    await startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap');
    expect(invokeCalls.map((c) => c.command)).not.toContain('set_workspace');
  });

  it('p0b_r5_frontend_never_invokes_execute_approved', async () => {
    const { startApprovedArtifactDownload } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };
    await startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap');
    expect(invokeCalls.map((c) => c.command)).not.toContain('execute_approved');
  });

  it('p0b_r5_approval_and_execution_use_same_semantic_input', async () => {
    const { startApprovedArtifactDownload } = await import('../src/lib/bridge/modelGateway');
    approvalResponse = validEnvelope('artifact.download');
    protectedResponse = {
      job_id: 'd'.repeat(64), artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap', lifecycle: 'awaiting_confirmation',
      expected_bytes: 1000, received_bytes: 0, percent: 0, started_utc_ms: 1, updated_utc_ms: 1, error_code: null
    };
    await startApprovedArtifactDownload('llama-cpp-windows-x86-64-cpu-bootstrap');
    const approvalCall = invokeCalls.find((c) => c.command === 'request_approval');
    const executionCall = invokeCalls.find((c) => c.command === 'start_approved_artifact_download');
    const approvalInput = approvalCall?.args?.input as { artifact_id: string };
    expect(approvalInput.artifact_id).toBe('llama-cpp-windows-x86-64-cpu-bootstrap');
    expect(executionCall?.args?.artifactId).toBe('llama-cpp-windows-x86-64-cpu-bootstrap');
  });
});
