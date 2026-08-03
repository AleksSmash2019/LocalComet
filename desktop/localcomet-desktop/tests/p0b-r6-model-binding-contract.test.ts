import { describe, expect, it, vi, beforeEach } from 'vitest';
import manifest from '../../../security/contracts/approval_command_families_v1.json';

const MANIFEST_FAMILIES: string[] = manifest.families;

function validEnvelope(overrides: Record<string, unknown> = {}) {
  return {
    token: 'lcap_' + 'a'.repeat(64),
    approvalId: 'appr_' + 'b'.repeat(32),
    callId: 'call_' + 'c'.repeat(32),
    tool: 'model.binding.set',
    riskLevel: 'guarded',
    commandFamily: 'model_binding_set',
    expiresAtUnixMs: Date.now() + 60_000,
    ...overrides
  };
}

const invokeCalls: Array<{ cmd: string; args: unknown }> = [];
let approvalResponse: unknown = validEnvelope();
let protectedResponse: unknown = {
  provider_id: 'openai-compatible-local',
  harness_id: 'minimal',
  host: '127.0.0.1',
  port: 1234,
  base_path: '/v1',
  model_id: 'test-model',
  binding_fingerprint: 'a'.repeat(64),
  discovered_fingerprint: 'b'.repeat(64),
  persistence: false
};
let approvalShouldThrow = false;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (cmd: string, args: unknown) => {
    invokeCalls.push({ cmd, args });
    if (cmd === 'request_approval') {
      if (approvalShouldThrow) throw new Error('prompt unavailable');
      return approvalResponse;
    }
    return protectedResponse;
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async () => () => {})
}));

beforeEach(() => {
  invokeCalls.length = 0;
  approvalResponse = validEnvelope();
  protectedResponse = {
    provider_id: 'openai-compatible-local',
    harness_id: 'minimal',
    host: '127.0.0.1',
    port: 1234,
    base_path: '/v1',
    model_id: 'test-model',
    binding_fingerprint: 'a'.repeat(64),
    discovered_fingerprint: 'b'.repeat(64),
    persistence: false
  };
  approvalShouldThrow = false;
});

describe('p0b-r6-model-binding-contract', () => {
  it('p0b_r6_frontend_model_binding_sends_no_confirmed', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: 'minimal',
      port: 1234,
      modelId: 'test-model'
    });
    const serialized = JSON.stringify(invokeCalls);
    expect(serialized).not.toContain('"confirmed"');
    expect(serialized).not.toContain('confirmed');
  });

  it('p0b_r6_frontend_model_binding_passes_token', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: 'minimal',
      port: 1234,
      modelId: 'test-model'
    });
    const bindingCall = invokeCalls.find(c => c.cmd === 'model_binding_set');
    expect(bindingCall).toBeDefined();
    const args = bindingCall!.args as Record<string, unknown>;
    expect(args.token).toBe('lcap_' + 'a'.repeat(64));
  });

  it('p0b_r6_frontend_model_binding_passes_approval_id', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: 'minimal',
      port: 1234,
      modelId: 'test-model'
    });
    const bindingCall = invokeCalls.find(c => c.cmd === 'model_binding_set');
    expect(bindingCall).toBeDefined();
    const args = bindingCall!.args as Record<string, unknown>;
    expect(args.approvalId).toBe('appr_' + 'b'.repeat(32));
  });

  it('p0b_r6_frontend_model_binding_passes_call_id', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: 'minimal',
      port: 1234,
      modelId: 'test-model'
    });
    const bindingCall = invokeCalls.find(c => c.cmd === 'model_binding_set');
    expect(bindingCall).toBeDefined();
    const args = bindingCall!.args as Record<string, unknown>;
    expect(args.callId).toBe('call_' + 'c'.repeat(32));
  });

  it('p0b_r6_frontend_approval_and_execution_inputs_equal', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: 'minimal',
      port: 1234,
      modelId: 'test-model'
    });
    const approvalCall = invokeCalls.find(c => c.cmd === 'request_approval');
    const bindingCall = invokeCalls.find(c => c.cmd === 'model_binding_set');
    expect(approvalCall).toBeDefined();
    expect(bindingCall).toBeDefined();
    const approvalInput = (approvalCall!.args as Record<string, unknown>).input as Record<string, unknown>;
    const bindingArgs = bindingCall!.args as Record<string, unknown>;
    expect(approvalInput.provider_id).toBe(bindingArgs.providerId);
    expect(approvalInput.harness_id).toBe(bindingArgs.harnessId);
    expect(approvalInput.model_id).toBe(bindingArgs.modelId);
    expect(approvalInput.port).toBe(bindingArgs.port);
  });

  it('p0b_r6_frontend_rejection_prevents_binding_invoke', async () => {
    approvalResponse = { code: 'approval_rejected', message: 'rejected' };
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await expect(
      setModelBinding({
        providerId: 'openai-compatible-local',
        harnessId: 'minimal',
        port: 1234,
        modelId: 'test-model'
      })
    ).rejects.toBeTruthy();
    const bindingCall = invokeCalls.find(c => c.cmd === 'model_binding_set');
    expect(bindingCall).toBeUndefined();
  });

  it('p0b_r6_frontend_prompt_failure_prevents_binding_invoke', async () => {
    approvalShouldThrow = true;
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await expect(
      setModelBinding({
        providerId: 'openai-compatible-local',
        harnessId: 'minimal',
        port: 1234,
        modelId: 'test-model'
      })
    ).rejects.toBeTruthy();
    const bindingCall = invokeCalls.find(c => c.cmd === 'model_binding_set');
    expect(bindingCall).toBeUndefined();
  });

  it('p0b_r6_frontend_family_manifest_matches_runtime_set', async () => {
    const { validateApprovalEnvelope } = await import('../src/lib/bridge/approval');
    const acceptedFamilies: string[] = [];
    for (const family of MANIFEST_FAMILIES) {
      try {
        validateApprovalEnvelope(validEnvelope({ commandFamily: family, tool: 'artifact.download' }), 'artifact.download');
        acceptedFamilies.push(family);
      } catch {
        // not accepted
      }
    }
    expect(acceptedFamilies.sort()).toEqual([...MANIFEST_FAMILIES].sort());
  });

  it('p0b_r6_frontend_accepts_all_rust_family_values', async () => {
    const { validateApprovalEnvelope } = await import('../src/lib/bridge/approval');
    const rustFamilies = [
      'artifact_download',
      'artifact_remove',
      'runtime_start',
      'runtime_stop',
      'model_binding_set',
      'tool_filesystem_read',
      'tool_filesystem_write',
      'tool_filesystem_delete'
    ];
    for (const family of rustFamilies) {
      const envelope = validEnvelope({ commandFamily: family, tool: 'artifact.download' });
      expect(() => validateApprovalEnvelope(envelope, 'artifact.download')).not.toThrow();
    }
  });

  it('p0b_r6_frontend_rejects_unknown_family', async () => {
    const { validateApprovalEnvelope } = await import('../src/lib/bridge/approval');
    const envelope = validEnvelope({ commandFamily: 'unknown_family' });
    expect(() => validateApprovalEnvelope(envelope, 'model.binding.set')).toThrow();
  });

  it('p0b_r6_frontend_current_routes_use_valid_families', async () => {
    const { validateApprovalEnvelope } = await import('../src/lib/bridge/approval');
    const routes: Array<[string, string]> = [
      ['artifact.download', 'artifact_download'],
      ['artifact.remove', 'artifact_remove'],
      ['runtime.start', 'runtime_start'],
      ['runtime.stop', 'runtime_stop'],
      ['model.binding.set', 'model_binding_set']
    ];
    for (const [tool, family] of routes) {
      const envelope = validEnvelope({ commandFamily: family, tool });
      expect(() => validateApprovalEnvelope(envelope, tool)).not.toThrow();
    }
  });

  it('p0b_r6_frontend_never_sends_renderer_approval_boolean', async () => {
    const { setModelBinding } = await import('../src/lib/bridge/modelGateway');
    await setModelBinding({
      providerId: 'openai-compatible-local',
      harnessId: 'minimal',
      port: 1234,
      modelId: 'test-model'
    });
    const serialized = JSON.stringify(invokeCalls);
    expect(serialized).not.toContain('userDecision');
    expect(serialized).not.toContain('user_decision');
    expect(serialized).not.toContain('"approved"');
    expect(serialized).not.toContain('"force"');
  });

  it('p0b_r6_frontend_tool_filesystem_read_family_accepted', async () => {
    const { validateApprovalEnvelope } = await import('../src/lib/bridge/approval');
    const envelope = validEnvelope({ commandFamily: 'tool_filesystem_read', tool: 'files.read' });
    expect(() => validateApprovalEnvelope(envelope, 'files.read')).not.toThrow();
  });

  it('p0b_r6_frontend_tool_filesystem_write_family_accepted', async () => {
    const { validateApprovalEnvelope } = await import('../src/lib/bridge/approval');
    const envelope = validEnvelope({ commandFamily: 'tool_filesystem_write', tool: 'files.write' });
    expect(() => validateApprovalEnvelope(envelope, 'files.write')).not.toThrow();
  });
});
