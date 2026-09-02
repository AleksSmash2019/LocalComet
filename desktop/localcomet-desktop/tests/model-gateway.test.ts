import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import ModelGatewayPanel from '../src/lib/components/model/ModelGatewayPanel.svelte';
import ManagedRuntimePanel from '../src/lib/components/model/ManagedRuntimePanel.svelte';
import { t } from '../src/lib/i18n';
import {
  getModelGatewayCatalog,
  getManagedRuntimeCapability,
  listModelGatewayModels,
  probeModelGateway,
  setModelBinding,
  startModelTurn,
  subscribeModelGatewayEvents
} from '../src/lib/bridge/modelGateway';
import {
  applyModelGatewayEvent,
  cancelLocalModelTurn,
  inferenceRequestStore,
  managedRuntimeStore,
  modelGatewayStore,
  startLocalModelTurn,
  resetModelGatewayStore,
  setGatewayPortText
} from '../src/lib/stores/modelGateway';
import { appendAcceptedChatTurn, chatMessages, resetShellStores, setAgentPermissions } from '../src/lib/stores/shellStore';
import { deriveBoundedNotepadTypeContinuation } from '../src/lib/tools/computerUseContinuation';
import type { ModelGatewayEvent } from '../src/lib/types/modelGateway';
import phaseCContract from '../../../security/contracts/adr015_tool_event_parity_v1.json';

const TURN_ID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const FINGERPRINT = 'b'.repeat(64);
const TRUST_CATALOG = {
  schema_version: 1,
  catalog_id: 'localcomet-approved-artifacts',
  catalog_version: '1.0.0',
  catalog_digest: 'c'.repeat(64)
};
let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let capabilityResponse: unknown = null;
let listener: ((event: { payload: unknown }) => void) | null = null;
let runToolCallResponse: unknown = null;
let observeResponse: unknown = null;
let runtimeStatusResponse: unknown = null;
// Mock-scoped: after the first revoke the broker grant must reject a replay.
let continuationRevoked = false;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    invokeCalls.push({ command, args });
    if (command === 'cu_broker_observe') return observeResponse;
    if (command === 'cu_broker_continuation_consume') {
      if (continuationRevoked) {
        throw { code: 'continuation_replayed', message: 'continuation_replayed' };
      }
      return { schema_version: 'cu.broker.continuation.grant.v1', status: 'leased', lease_id: `lease_${invokeCalls.length}`, grant_state: 'in_flight' };
    }
    if (command === 'cu_broker_continuation_complete') {
      const status = (args as { status?: string }).status;
      return { schema_version: 'cu.broker.continuation.grant.v1', status, grant_state: status === 'verified' ? 'completed_verified' : 'issued' };
    }
    if (command === 'cu_broker_continuation_revoke') {
      continuationRevoked = true;
      return { revoked: 1 };
    }
    if (command === 'model_turn_cancel') {
      return { request_id: args?.requestId, turn_id: args?.requestId, state: 'Cancelled', accepted: true, already_terminal: false, worker_alive: false };
    }
    if (command === 'request_approval') {
      const tool = (args as { tool: string }).tool;
      const familyMap: Record<string, string> = { 'artifact.download': 'artifact_download', 'artifact.remove': 'artifact_remove', 'runtime.start': 'runtime_start', 'runtime.stop': 'runtime_stop', 'model.binding.set': 'model_binding_set' };
      return { token: `lcap_${'a'.repeat(64)}`, approvalId: `appr_${'b'.repeat(32)}`, callId: `call_${'c'.repeat(32)}`, tool, riskLevel: 'guarded', commandFamily: familyMap[tool] ?? 'model_binding_set', expiresAtUnixMs: Date.now() + 300_000 };
    }
    if (command === 'run_tool_call') {
      const input = args?.input as { action?: unknown } | undefined;
      if (input?.action === 'type') {
        return { ...(runToolCallResponse as Record<string, unknown>), action: { kind: 'type', target: 'notepad' } };
      }
      return runToolCallResponse;
    }
    if (command === 'model_gateway_catalog') return catalogFixture();
    if (command === 'managed_runtime_status') return runtimeStatusResponse ?? { engine: 'llama.cpp', state: 'NotInstalled', installation: 'Not installed', runtime_version: null, runtime_id: null, runtime_instance_id: null, runtime_instance_fingerprint: null, model_id: null, model_display_name: null, binding_fingerprint: null, model_state: 'Unavailable', inference_ready: false, last_error: null };
    if (command === 'managed_runtime_catalog') return { ...TRUST_CATALOG, runtimes: [] };
    if (command === 'managed_model_catalog') return { ...TRUST_CATALOG, engine: 'llama.cpp', model_root: '<MANAGED_MODEL_ROOT>', models: [], maximum_models: 32 };
    if (command === 'managed_installed_artifacts') return { ...TRUST_CATALOG, artifacts: [] };
    if (command === 'managed_runtime_logs') return { stdout_tail: [], stderr_tail: [] };
    if (command === 'managed_runtime_capability') return capabilityResponse;
    if (command === 'model_gateway_probe') return { status: 'Ready', provider_id: 'openai-compatible-local', host: '127.0.0.1', port: args?.port, base_path: '/v1', model_count: 1 };
    if (command === 'model_gateway_list_models') return { provider_id: 'openai-compatible-local', host: '127.0.0.1', port: args?.port, models: [{ model_id: 'local-model' }], discovered_fingerprint: FINGERPRINT };
    if (command === 'model_binding_set') return { provider_id: 'openai-compatible-local', harness_id: args?.harnessId, host: '127.0.0.1', port: args?.port, base_path: '/v1', model_id: args?.modelId, binding_fingerprint: FINGERPRINT, discovered_fingerprint: FINGERPRINT, persistence: false };
    if (command === 'model_turn_start') return {
      request_id: args?.requestId,
      chat_session_id: args?.chatSessionId,
      turn_id: args?.requestId,
      state: 'Accepted',
      model_id: args?.modelId,
      submitted_at_unix_ms: args?.submittedAtUnixMs,
      max_tokens: args?.maxTokens,
      seed: args?.seed,
      effort: args?.effort ?? 'off',
      binding_fingerprint: args?.bindingFingerprint,
      ...(Array.isArray(args?.fileIds) && args.fileIds.length > 0 ? {
        file_context: {
          source_bytes: 10,
          source_characters: 10,
          included_bytes: 5,
          included_characters: 5,
          truncated: true,
          files: [{ file_id: args.fileIds[0], filename: 'notes.md', original_bytes: 10, original_characters: 10, included_bytes: 5, included_characters: 5, inclusion: 'bounded_excerpt' }]
        }
      } : {})
    };
    return {};
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_event: string, callback: (event: { payload: unknown }) => void): Promise<() => void> => {
    listener = callback;
    return () => undefined;
  })
}));

function installTauriMock(): void {
  invokeCalls = [];
  listener = null;
  observeResponse = null;
  runtimeStatusResponse = null;
  continuationRevoked = false;
  delete (globalThis as { __LOCALCOMET_CONTINUATION_TRACE?: unknown[] }).__LOCALCOMET_CONTINUATION_TRACE;
  // Full verified v1 envelope: the only shape the shared classifier accepts
  // as a PASS; the legacy bare ok=true now stays honestly UNVERIFIED.
  runToolCallResponse = {
    tool: 'computer_use',
    schema_version: 'computer_use.result.v1',
    status: 'completed',
    terminal: true,
    succeeded: true,
    verification: 'verified',
    action: { kind: 'open_app', target: 'Calculator' }
  };
  capabilityResponse = {
    runtime_id: 'llama-cpp-windows-x86-64-vulkan-bootstrap',
    available: true,
    safe_to_start: true,
    reason_code: null,
    fallback_runtime_ids: [],
    device_summary: 'NVIDIA GeForce RTX 5070 (11943 MiB)',
    launch_recommendation: null
  };
}

function catalogFixture() {
  return {
    gateway_version: 'v6.84.5',
    providers: [
      { provider_id: 'openai-compatible-local', label: 'OpenAI-compatible local', scheme: 'http', host: '127.0.0.1', base_path: '/v1' },
      { provider_id: 'managed-llama-cpp', label: 'LocalComet managed llama.cpp', scheme: 'internal', host: '127.0.0.1', base_path: '/v1' }
    ],
    harnesses: [{ harness_id: 'minimal', label: 'Minimal' }, { harness_id: 'native-localcomet', label: 'Native LocalComet' }],
    persistence: false,
    tools_available: false
  };
}

function modelEvent(method: ModelGatewayEvent['method'], sequence: number, patch: Partial<ModelGatewayEvent> = {}): ModelGatewayEvent {
  const stateByMethod = {
    'model.turn.started': 'Streaming',
    'model.output.delta': 'Streaming',
    'model.turn.completed': 'Completed',
    'model.turn.cancelled': 'Cancelled',
    'model.turn.timed_out': 'TimedOut',
    'model.turn.failed': 'Failed',
    'model.tool.request': 'Streaming',
    'model.turn.tool_calls': 'ToolCalls'
  } as const;
  return {
    method,
    sequence,
    reply_to: TURN_ID,
    request_id: TURN_ID,
    chat_session_id: 'local-chat',
    turn_id: TURN_ID,
    state: patch.state ?? stateByMethod[method],
    text: patch.text ?? null,
    model_called: patch.model_called ?? true,
    tools_executed: patch.tools_executed ?? 0,
    ...(patch.tool_calls ? { tool_calls: patch.tool_calls } : {}),
    persistence: false,
    generated_bytes: patch.generated_bytes ?? 0,
    provider_id: 'openai-compatible-local',
    harness_id: 'minimal',
    model_id: 'local-model',
    binding_fingerprint: FINGERPRINT
  };
}

describe('Local Model Gateway frontend', () => {
  it('derives a bounded Notepad paste continuation without broadening the target scope', () => {
    expect(deriveBoundedNotepadTypeContinuation(
      'Открой Блокнот и вставь в нём: LocalComet paste smoke.',
      { name: 'computer_use', arguments: { action: 'open_app', target: 'notepad' } }
    )).toEqual({ name: 'computer_use', arguments: { action: 'paste', text: 'LocalComet paste smoke.' } });
    expect(deriveBoundedNotepadTypeContinuation(
      'Открой Калькулятор и вставь в нём: no.',
      { name: 'computer_use', arguments: { action: 'open_app', target: 'calculator' } }
    )).toBeNull();
  });

  beforeEach(() => {
    vi.useRealTimers();
    resetModelGatewayStore();
    resetShellStores();
    installTauriMock();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('uses exactly the fixed model gateway commands', async () => {
    await getModelGatewayCatalog();
    await probeModelGateway(1234);
    await listModelGatewayModels(1234);
    await setModelBinding({ providerId: 'openai-compatible-local', harnessId: 'minimal', port: 1234, modelId: 'local-model' });
    await startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, seed: 42, effort: 'off', prompt: 'hello', locale: 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false }, messages: [] });
    expect(invokeCalls.map((call) => call.command)).toEqual([
      'model_gateway_catalog',
      'model_gateway_probe',
      'model_gateway_list_models',
      'request_approval',
      'model_binding_set',
      'model_turn_start'
    ]);
    expect(JSON.stringify(invokeCalls)).not.toContain('http://');
    expect(JSON.stringify(invokeCalls)).not.toContain('api');
    // Frozen model.turn.start contract: the invoke arguments must carry exactly
    // the parameters of the Rust `model_turn_start` command
    // (request_id, chat_session_id, model_id, submitted_at_unix_ms, max_tokens,
    // prompt, file_ids, locale, binding_fingerprint) and nothing else.
    expect(invokeCalls.at(-1)?.args).toEqual({
      requestId: TURN_ID,
      chatSessionId: 'local-chat',
      modelId: 'local-model',
      submittedAtUnixMs: 1,
      maxTokens: 256,
      seed: 42,
      effort: 'off',
      prompt: 'hello',
      fileIds: [],
      locale: 'ru',
      bindingFingerprint: FINGERPRINT,
      agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false },
      messages: []
    });
    expect(Object.keys(invokeCalls.at(-1)?.args ?? {}).sort()).toEqual([
      'agentPermissions',
      'bindingFingerprint',
      'chatSessionId',
      'effort',
      'fileIds',
      'locale',
      'maxTokens',
      'messages',
      'modelId',
      'prompt',
      'requestId',
      'seed',
      'submittedAtUnixMs'
    ]);
  });

  it('passes only validated opaque file identities to the model command', async () => {
    const fileId = 'd'.repeat(64);
    const response = await startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, seed: 42, prompt: 'hello', fileIds: [fileId], locale: 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false }, messages: [] });
    expect(invokeCalls.at(-1)?.args?.fileIds).toEqual([fileId]);
    expect(response.file_context).toMatchObject({ included_bytes: 5, truncated: true });
    await expect(startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, seed: 42, prompt: 'hello', fileIds: ['C:\\temp\\notes.md'], locale: 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false }, messages: [] })).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(1);
  });

  it('rejects invalid ports before invoking Tauri', async () => {
    await expect(probeModelGateway(80)).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);
    setGatewayPortText('12x34');
    expect(get(modelGatewayStore).portText).toBe('1234');
  });

  it('rejects an unknown assistant locale before invoking Tauri', async () => {
    await expect(startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, seed: 42, prompt: 'hello', locale: 'xx' as 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false }, messages: [] })).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);
  });

  it('parses cumulative tool request and terminal telemetry and rejects disabled nonzero telemetry', async () => {
    const seen: ModelGatewayEvent[] = [];
    const errors: string[] = [];
    await subscribeModelGatewayEvents(
      (event) => seen.push(event),
      (error) => errors.push(error.code),
      { toolsEnabled: true }
    );
    const calls = [
      { id: 'call_1', name: 'files.read', arguments: { path: 'a.txt' } },
      { id: 'call_2', name: 'files.list', arguments: { path: '.' } }
    ];
    const payload = (method: string, sequence: number, state: string, toolsExecuted: unknown, toolCalls?: unknown) => ({
      method, sequence, reply_to: TURN_ID, request_id: TURN_ID, chat_session_id: 'local-chat', turn_id: TURN_ID,
      model_id: 'local-model', state, text: null,
      metadata: { model_called: true, tools_executed: toolsExecuted, persistence: false, generated_bytes: 0, provider_id: 'openai-compatible-local', harness_id: 'minimal', binding_fingerprint: FINGERPRINT, ...(toolCalls ? { tool_calls: toolCalls } : {}) }
    });
    listener?.({ payload: payload('model.tool.request', 0, 'Streaming', 1, [calls[0]]) });
    listener?.({ payload: payload('model.turn.tool_calls', 1, 'ToolCalls', 2, calls) });
    listener?.({ payload: payload('model.output.delta', 2, 'Streaming', 1) });
    expect(seen.map((event) => [event.method, event.tools_executed])).toEqual([
      ['model.tool.request', 1],
      ['model.turn.tool_calls', 2]
    ]);
    expect(errors).toEqual(['invalid_payload']);
  });

  it('rejects malformed non-string tool call identities', async () => {
    const errors: string[] = [];
    await subscribeModelGatewayEvents(() => { throw new Error('malformed tool call reached consumer'); }, (error) => errors.push(error.code), { toolsEnabled: true });
    for (const badCall of [
      { id: null, name: 'files.read', arguments: { path: 'a.txt' } },
      { id: 'call_1', name: 42, arguments: { path: 'a.txt' } },
      { name: 'files.read', arguments: { path: 'a.txt' } }
    ]) {
      listener?.({ payload: {
        method: 'model.tool.request', sequence: 0, reply_to: TURN_ID, request_id: TURN_ID,
        chat_session_id: 'local-chat', turn_id: TURN_ID, model_id: 'local-model', state: 'Streaming', text: null,
        metadata: { model_called: true, tools_executed: 1, persistence: false, generated_bytes: 0, provider_id: 'openai-compatible-local', harness_id: 'minimal', binding_fingerprint: FINGERPRINT, tool_calls: [badCall] }
      } });
    }
    expect(errors).toEqual(['invalid_payload', 'invalid_payload', 'invalid_payload']);
  });

  it('accepts the shared Phase C tool-event contract only when tools are enabled', async () => {
    const { identity, enabled, disabled } = phaseCContract;
    const eventPayload = (event: typeof enabled.events[number]) => ({
      method: event.method,
      sequence: event.sequence,
      reply_to: identity.requestId,
      request_id: identity.requestId,
      chat_session_id: identity.chatSessionId,
      turn_id: identity.requestId,
      model_id: identity.modelId,
      state: event.state,
      text: null,
      metadata: {
        model_called: true,
        tools_executed: event.toolsExecuted,
        persistence: false,
        generated_bytes: 0,
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        binding_fingerprint: identity.bindingFingerprint,
        tool_calls: event.toolCalls
      }
    });
    const seen: ModelGatewayEvent[] = [];
    const errors: string[] = [];
    await subscribeModelGatewayEvents(
      (event) => seen.push(event),
      (error) => errors.push(error.code),
      { toolsEnabled: true }
    );
    for (const event of enabled.events) listener?.({ payload: eventPayload(event) });
    expect(seen.map((event) => [event.method, event.tools_executed, event.tool_calls])).toEqual(
      enabled.events.map((event) => [event.method, event.toolsExecuted, event.toolCalls])
    );
    expect(errors).toEqual([]);

    const rejected: string[] = [];
    await subscribeModelGatewayEvents(
      () => { throw new Error('tool event must not reach a disabled turn'); },
      (error) => rejected.push(error.code)
    );
    listener?.({ payload: eventPayload(disabled) });
    expect(rejected).toEqual(['invalid_payload']);
  });

  it('rejects tool events when the turn did not enable tools', async () => {
    const seen: ModelGatewayEvent[] = [];
    const errors: string[] = [];
    await subscribeModelGatewayEvents((event) => seen.push(event), (error) => errors.push(error.code));
    listener?.({ payload: {
      method: 'model.tool.request', sequence: 0, reply_to: TURN_ID, request_id: TURN_ID,
      chat_session_id: 'local-chat', turn_id: TURN_ID, model_id: 'local-model', state: 'Streaming', text: null,
      metadata: {
        model_called: true, tools_executed: 1, persistence: false, generated_bytes: 0,
        provider_id: 'openai-compatible-local', harness_id: 'minimal', binding_fingerprint: FINGERPRINT,
        tool_calls: [{ id: 'call_1', name: 'files.read', arguments: { path: 'a.txt' } }]
      }
    } });
    expect(seen).toEqual([]);
    expect(errors).toEqual(['invalid_payload']);
  });

  it('routes allowlisted computer_use through scoped approval when enabled', async () => {
    setAgentPermissions({ computerUse: true });
    modelGatewayStore.update((state) => ({
      ...state,
      binding: {
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        host: '127.0.0.1',
        port: 1234,
        base_path: '/v1',
        model_id: 'local-model',
        binding_fingerprint: FINGERPRINT,
        discovered_fingerprint: FINGERPRINT,
        persistence: false
      }
    }));
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, effort: 'off', chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
    appendAcceptedChatTurn(TURN_ID, 'Открой калькулятор');

    applyModelGatewayEvent(modelEvent('model.turn.started', 0));
    applyModelGatewayEvent(modelEvent('model.tool.request', 1, {
      tools_executed: 1,
      tool_calls: [{ id: 'call_1', name: 'computer_use', arguments: { action: 'open_app', target: 'Calculator' } }]
    }));
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('completed'));

    expect(invokeCalls.map((call) => call.command)).toContain('run_tool_call');
    expect(invokeCalls.map((call) => call.command)).toContain('request_approval');
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    const assistant = get(chatMessages);
    expect(assistant.find((message) => message.role === 'assistant' && message.requestId === TURN_ID)?.toolCalls?.[0]?.status).toBe('PASS');
  });

  it('projects completed not_applicable Computer Use actions as PASS', async () => {
    setAgentPermissions({ computerUse: true });
    runToolCallResponse = {
      tool: 'computer_use',
      schema_version: 'computer_use.result.v1',
      status: 'completed',
      terminal: true,
      succeeded: true,
      verification: 'not_applicable',
      action: { kind: 'press_key', target: 'enter' }
    };
    modelGatewayStore.update((state) => ({
      ...state,
      binding: {
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        host: '127.0.0.1',
        port: 1234,
        base_path: '/v1',
        model_id: 'local-model',
        binding_fingerprint: FINGERPRINT,
        discovered_fingerprint: FINGERPRINT,
        persistence: false
      }
    }));
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, effort: 'off', chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
    appendAcceptedChatTurn(TURN_ID, 'Нажми Enter');

    applyModelGatewayEvent(modelEvent('model.turn.started', 0));
    applyModelGatewayEvent(modelEvent('model.tool.request', 1, {
      tools_executed: 1,
      tool_calls: [{ id: 'call_1', name: 'computer_use', arguments: { action: 'key', text: 'enter' } }]
    }));
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('completed'));

    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    const assistant = get(chatMessages);
    expect(assistant.find((message) => message.role === 'assistant' && message.requestId === TURN_ID)?.toolCalls?.[0]?.status).toBe('PASS');

    applyModelGatewayEvent(modelEvent('model.turn.tool_calls', 2, {
      tools_executed: 1,
      tool_calls: [{ id: 'call_1', name: 'computer_use', arguments: { action: 'key', text: 'enter' } }]
    }));
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    expect(get(chatMessages).find((message) => message.role === 'assistant' && message.requestId === TURN_ID)?.toolCalls?.[0]?.status).toBe('PASS');
  });

  it('executes exactly one correlated type continuation after verified Notepad open', async () => {
    setAgentPermissions({ computerUse: true, tools: true });
    const runtimeId = 'a'.repeat(32);
    const runtimeInstanceId = 'b'.repeat(32);
    const runtimeStatus = {
      engine: 'llama.cpp' as const,
      state: 'Ready' as const,
      installation: 'Installed' as const,
      runtime_version: 'test',
      runtime_id: runtimeId,
      runtime_instance_id: runtimeInstanceId,
      runtime_instance_fingerprint: 'f'.repeat(64),
      model_id: 'local-model',
      model_display_name: 'Local test model',
      binding_fingerprint: FINGERPRINT,
      model_state: 'Ready' as const,
      inference_ready: true as const,
      last_error: null,
      loading_phase: null
    };
    runtimeStatusResponse = runtimeStatus;
    const runtimeBinding = {
      provider_id: 'managed-llama-cpp' as const,
      harness_id: 'minimal' as const,
      host: '127.0.0.1' as const,
      port: 1234,
      base_path: '/v1' as const,
      model_id: 'local-model',
      runtime_instance_id: runtimeInstanceId,
      binding_fingerprint: FINGERPRINT,
      discovered_fingerprint: FINGERPRINT,
      persistence: false as const
    };
    managedRuntimeStore.update((state) => ({
      ...state,
      selectedModelId: 'local-model',
      harnessId: 'minimal',
      status: runtimeStatus,
      catalog: [{
        model_id: 'local-model', provider: 'test', family: 'test', display_name: 'Local test model', format: 'GGUF', quantization: 'Q4_K_M',
        upstream_repository: 'test', upstream_revision: 'test', asset_filename: 'test.gguf', asset_bytes: 1, asset_sha256: 'd'.repeat(64),
        license_id: 'test', compatible_runtime_ids: [runtimeId], public_distribution: false, installer_bundled: false,
        bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION', status: 'approved_internal_bootstrap', trust_kind: 'approved_catalog'
      }],
      runtimeCatalog: [{
        runtime_id: runtimeId, provider: 'test', release_tag: 'test', platform: 'windows', architecture: 'x86-64', variant: 'cpu',
        upstream_repository: 'test', upstream_revision: 'test', asset_filename: 'test.zip', asset_bytes: 1, asset_sha256: 'e'.repeat(64),
        archive_format: 'zip', permitted_bind_scope: 'loopback-only', supported_api_protocol: 'openai-compatible-v1', license_id: 'test',
        public_distribution: false, status: 'approved_internal_bootstrap'
      }],
      installedArtifacts: [
        { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: 'c'.repeat(64), artifact_id: 'local-model', kind: 'model', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 1, expected_sha256: 'd'.repeat(64), observed_bytes: 1, observed_sha256: 'd'.repeat(64), validation_code: 'ok', verified_unix_ms: 1 },
        { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: 'c'.repeat(64), artifact_id: runtimeId, kind: 'runtime', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 1, expected_sha256: 'e'.repeat(64), observed_bytes: 1, observed_sha256: 'e'.repeat(64), validation_code: 'ok', verified_unix_ms: 1 }
      ],
      readiness: {
        schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: 'c'.repeat(64), model_id: 'local-model',
        model_trust_kind: 'approved_catalog', model_status: 'valid', compatible_runtime_ids: [runtimeId], selected_runtime_id: runtimeId,
        runtime_status: 'valid', compatibility: 'compatible', readiness: 'ready', launchable: true
      },
      binding: runtimeBinding
    }));
    modelGatewayStore.update((state) => ({ ...state, binding: runtimeBinding }));

    const accepted = await startLocalModelTurn('Открой Блокнот и напечатай в нём: LocalComet isolated smoke test.', 'local-chat');
    expect(accepted).toBe(true);
    const requestId = get(inferenceRequestStore).requestId;
    expect(requestId).toMatch(/^[0-9a-f]{24}$/);
    const eventForTurn = (method: ModelGatewayEvent['method'], sequence: number, patch: Partial<ModelGatewayEvent> = {}): ModelGatewayEvent => ({
      ...modelEvent(method, sequence, patch),
      request_id: requestId!,
      reply_to: requestId!,
      turn_id: requestId!,
      provider_id: 'managed-llama-cpp'
    });
    applyModelGatewayEvent(eventForTurn('model.turn.started', 0));
    applyModelGatewayEvent(eventForTurn('model.tool.request', 1, {
      tools_executed: 1,
      tool_calls: [{ id: 'call_11111111111111111111111111111111', name: 'computer_use', arguments: { action: 'open_app', target: 'notepad' } }]
    }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    const toolInvokes = invokeCalls.filter((call) => call.command === 'run_tool_call');
    expect(toolInvokes).toHaveLength(2);
    expect((toolInvokes[0].args?.input as Record<string, unknown>).action).toBe('open_app');
    expect((toolInvokes[1].args?.input as Record<string, unknown>)).toEqual({ action: 'type', text: 'LocalComet isolated smoke test.' });
    expect(toolInvokes[0].args?.requestId).toBe(requestId);
    expect(toolInvokes[1].args?.requestId).toBe(requestId);
    expect(toolInvokes[0].args?.actionId).toBe('call_11111111111111111111111111111111');
    expect(toolInvokes[1].args?.actionId).toMatch(/^call_[0-9a-f]{32}$/);
    expect(toolInvokes[1].args?.actionId).not.toBe(toolInvokes[0].args?.actionId);
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    const assistant = get(chatMessages).find((message) => message.role === 'assistant' && message.requestId === requestId);
    expect(assistant?.toolCalls).toHaveLength(2);
    expect(assistant?.toolCalls?.map((item) => item.status)).toEqual(['PASS', 'PASS']);
  });

  it('keeps a legacy unverified computer_use result out of PASS and completed', async () => {
    setAgentPermissions({ computerUse: true });
    runToolCallResponse = { tool: 'computer_use', ok: true, action: 'open_app', target: 'Calculator' };
    modelGatewayStore.update((state) => ({
      ...state,
      binding: {
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        host: '127.0.0.1',
        port: 1234,
        base_path: '/v1',
        model_id: 'local-model',
        binding_fingerprint: FINGERPRINT,
        discovered_fingerprint: FINGERPRINT,
        persistence: false
      }
    }));
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, effort: 'off', chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
    appendAcceptedChatTurn(TURN_ID, 'Открой калькулятор');

    applyModelGatewayEvent(modelEvent('model.turn.started', 0));
    applyModelGatewayEvent(modelEvent('model.tool.request', 1, {
      tools_executed: 1,
      tool_calls: [{ id: 'call_1', name: 'computer_use', arguments: { action: 'open_app', target: 'Calculator' } }]
    }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    // ok=true without the v1 envelope is at most an unverified success: the
    // turn must not claim completion and the card must not wear a PASS pill.
    expect(get(inferenceRequestStore).lifecycle).toBe('awaiting_verification');
    const assistant = get(chatMessages);
    expect(assistant.find((message) => message.role === 'assistant' && message.requestId === TURN_ID)?.toolCalls?.[0]?.status).toBe('UNVERIFIED');
  });

  it('marks the computer_use card FAIL when the backend returns an execution error', async () => {
    setAgentPermissions({ computerUse: true });
    runToolCallResponse = { tool: 'computer_use', ok: false, reason: 'launcher failed' };
    modelGatewayStore.update((state) => ({
      ...state,
      binding: {
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        host: '127.0.0.1',
        port: 1234,
        base_path: '/v1',
        model_id: 'local-model',
        binding_fingerprint: FINGERPRINT,
        discovered_fingerprint: FINGERPRINT,
        persistence: false
      }
    }));
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, effort: 'off', chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
    appendAcceptedChatTurn(TURN_ID, 'Открой калькулятор');

    applyModelGatewayEvent(modelEvent('model.turn.started', 0));
    applyModelGatewayEvent(modelEvent('model.tool.request', 1, {
      tools_executed: 1,
      tool_calls: [{ id: 'call_1', name: 'computer_use', arguments: { action: 'open_app', target: 'Calculator' } }]
    }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(get(inferenceRequestStore).lifecycle).toBe('failed');
    const assistant = get(chatMessages);
    const tool = assistant.find((message) => message.role === 'assistant' && message.requestId === TURN_ID)?.toolCalls?.[0];
    expect(tool?.status).toBe('FAIL');
    expect(tool?.result).toContain('launcher failed');
  });

  it('subscribes to model events and updates truthful telemetry', async () => {
    const seen: string[] = [];
    await subscribeModelGatewayEvents((event) => seen.push(event.method));
    listener?.({ payload: { method: 'model.output.delta', sequence: 1, reply_to: TURN_ID, request_id: TURN_ID, chat_session_id: 'local-chat', turn_id: TURN_ID, model_id: 'local-model', state: 'Streaming', text: 'hi', metadata: { model_called: true, tools_executed: 0, persistence: false, generated_bytes: 2, provider_id: 'openai-compatible-local', harness_id: 'minimal', model_id: 'local-model', binding_fingerprint: FINGERPRINT } } });
    expect(seen).toEqual(['model.output.delta']);
    modelGatewayStore.update((state) => ({
      ...state,
      binding: {
        provider_id: 'openai-compatible-local',
        harness_id: 'minimal',
        host: '127.0.0.1',
        port: 1234,
        base_path: '/v1',
        model_id: 'local-model',
        binding_fingerprint: FINGERPRINT,
        discovered_fingerprint: FINGERPRINT,
        persistence: false
      }
    }));
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, effort: 'off', chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
    appendAcceptedChatTurn(TURN_ID, 'hello');
    applyModelGatewayEvent(modelEvent('model.turn.started', 0));
    applyModelGatewayEvent(modelEvent('model.output.delta', 1, { text: 'hello' }));
    applyModelGatewayEvent(modelEvent('model.turn.completed', 2, { state: 'Completed' }));
    const state = get(modelGatewayStore);
    expect(state.modelCalled).toBe(true);
    expect(state.toolsExecuted).toBe(0);
    expect(state.persistence).toBe('Off');
    expect(state.status).toBe('Completed');
    expect(state.generatedText).toBe('hello');
  });

  it('renders no URL, API key, header, tool or attachment controls', () => {
    const body = render(ModelGatewayPanel).body;
    expect(body).toContain(get(t)('model.openai_compatible_local'));
    expect(body).toContain('127.0.0.1');
    expect(body).not.toMatch(/URL|API key|Headers|Temperature|Attachments|Tool controls/i);
  });

  it('renders managed runtime without URL, port, API-key, executable or path controls', () => {
    const body = render(ManagedRuntimePanel).body;
    expect(body).toContain(get(t)('model.managed_runtime_title'));
    expect(body).toContain(get(t)('model.not_installed'));
    expect(body).not.toMatch(/URL|Port|API key|Executable|Model path|Environment|Arguments/i);
  });

  it('invokes the capability command with exact args and a validated payload', async () => {
    const capability = await getManagedRuntimeCapability('llama-cpp-windows-x86-64-vulkan-bootstrap', 'qwen3-1.7b-instruct-q4-k-m');

    expect(invokeCalls.at(-1)).toEqual({
      command: 'managed_runtime_capability',
      args: { runtimeId: 'llama-cpp-windows-x86-64-vulkan-bootstrap', modelId: 'qwen3-1.7b-instruct-q4-k-m' }
    });
    expect(capability.available).toBe(true);
    expect(capability.safe_to_start).toBe(true);
    expect(capability.device_summary).toContain('RTX 5070');
    expect(capability.reason_code).toBeNull();
  });

  it('rejects capability payloads that invent or drop fields', async () => {
    // Defect caught: a payload with an extra key or a missing availability
    // flag must throw instead of surfacing an invented capability claim.
    capabilityResponse = {
      runtime_id: 'llama-cpp-windows-x86-64-vulkan-bootstrap',
      available: true,
      safe_to_start: true,
      reason_code: null,
      fallback_runtime_ids: [],
      device_summary: 'GPU',
      unexpected: true
    };
    await expect(getManagedRuntimeCapability('llama-cpp-windows-x86-64-vulkan-bootstrap')).rejects.toThrow();

    const { available, ...missingAvailability } = {
      runtime_id: 'llama-cpp-windows-x86-64-vulkan-bootstrap',
      available: true,
      safe_to_start: true,
      reason_code: null,
      fallback_runtime_ids: [],
      device_summary: null
    } as Record<string, unknown>;
    capabilityResponse = missingAvailability;
    await expect(getManagedRuntimeCapability('llama-cpp-windows-x86-64-vulkan-bootstrap')).rejects.toThrow();
  });

  it('preserves the vulkan-unavailable reason and fallback list from the backend', async () => {
    capabilityResponse = {
      runtime_id: 'llama-cpp-windows-x86-64-vulkan-bootstrap',
      available: false,
      safe_to_start: false,
      reason_code: 'VULKAN_DEVICE_UNAVAILABLE',
      fallback_runtime_ids: ['llama-cpp-windows-x86-64-cpu-bootstrap'],
      device_summary: null,
      launch_recommendation: null
    };

    const capability = await getManagedRuntimeCapability('llama-cpp-windows-x86-64-vulkan-bootstrap', 'qwen3-1.7b-instruct-q4-k-m');

    expect(capability.available).toBe(false);
    expect(capability.reason_code).toBe('VULKAN_DEVICE_UNAVAILABLE');
    expect(capability.fallback_runtime_ids).toEqual(['llama-cpp-windows-x86-64-cpu-bootstrap']);
    expect(capability.launch_recommendation).toBeNull();
  });

  it('validates a hardware-fit launch recommendation payload', async () => {
    capabilityResponse = {
      runtime_id: 'llama-cpp-windows-x86-64-vulkan-bootstrap',
      available: true,
      safe_to_start: true,
      reason_code: null,
      fallback_runtime_ids: [],
      device_summary: 'NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)',
      launch_recommendation: {
        mode: 'hybrid',
        gpu_layers: 29,
        ctx_size: 4096,
        architecture: 'qwen3',
        block_count: 48,
        model_context_length: 40960,
        estimated: false
      }
    };

    const capability = await getManagedRuntimeCapability('llama-cpp-windows-x86-64-vulkan-bootstrap', 'qwen3-1.7b-instruct-q4-k-m');

    expect(capability.launch_recommendation).toEqual({
      mode: 'hybrid',
      gpu_layers: 29,
      ctx_size: 4096,
      architecture: 'qwen3',
      block_count: 48,
      model_context_length: 40960,
      estimated: false
    });
  });

  it('rejects recommendation payloads with an inconsistent layer count', async () => {
    capabilityResponse = {
      runtime_id: 'llama-cpp-windows-x86-64-vulkan-bootstrap',
      available: true,
      safe_to_start: true,
      reason_code: null,
      fallback_runtime_ids: [],
      device_summary: 'NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)',
      launch_recommendation: {
        mode: 'hybrid',
        gpu_layers: null,
        ctx_size: 4096,
        architecture: 'qwen3',
        block_count: 48,
        model_context_length: 40960,
        estimated: false
      }
    };

    await expect(getManagedRuntimeCapability('llama-cpp-windows-x86-64-vulkan-bootstrap')).rejects.toThrow();
  });

  describe('bounded launch continuation (plan P0.2)', () => {
    function launchPendingEnvelope(): Record<string, unknown> {
      return {
        tool: 'computer_use',
        schema_version: 'computer_use.result.v1',
        action: { kind: 'open_app', target: 'Calculator' },
        status: 'launch_pending',
        terminal: false,
        succeeded: false,
        verification: 'pending',
        request_id: TURN_ID,
        reason: 'spawn accepted but the readiness postcondition has not been observed yet'
      };
    }

    async function startTurnWithPendingLaunch(withContinuation = false): Promise<void> {
      vi.useFakeTimers();
      setAgentPermissions({ computerUse: true });
      modelGatewayStore.update((state) => ({
        ...state,
        binding: {
          provider_id: 'openai-compatible-local',
          harness_id: 'minimal',
          host: '127.0.0.1',
          port: 1234,
          base_path: '/v1',
          model_id: 'local-model',
          binding_fingerprint: FINGERPRINT,
          discovered_fingerprint: FINGERPRINT,
          persistence: false
        }
      }));
      inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, effort: 'off', chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
      appendAcceptedChatTurn(TURN_ID, 'Открой калькулятор');
      runToolCallResponse = withContinuation
        ? {
            ...launchPendingEnvelope(),
            execution: {
              continuation: {
                schema_version: 'cu.broker.continuation.grant.v1',
                grant_ref: `cgr_${'d'.repeat(32)}`,
                grant_state: 'issued',
                step_index: 0,
                allowed_next_actions: ['observe', 'wait', 'wait_for_window'],
                remaining_steps: 2
              }
            }
          }
        : launchPendingEnvelope();
      applyModelGatewayEvent(modelEvent('model.turn.started', 0));
      applyModelGatewayEvent(modelEvent('model.tool.request', 1, {
        tools_executed: 1,
        tool_calls: [{ id: 'call_1', name: 'computer_use', arguments: { action: 'open_app', target: 'Calculator' } }]
      }));
      // Flush approval + run_tool_call microtasks before any timer fires.
      await vi.advanceTimersByTimeAsync(0);
    }

    const observeCalls = (): number =>
      invokeCalls.filter((call) => call.command === 'cu_broker_observe').length;

    it('polls cu_broker_observe to a verified terminal without respawn or new token', async () => {
      await startTurnWithPendingLaunch();
      expect(get(inferenceRequestStore).lifecycle).toBe('awaiting_verification');
      expect(observeCalls()).toBe(0);

      observeResponse = {
        found: true,
        envelope: {
          ...launchPendingEnvelope(),
          status: 'completed',
          terminal: true,
          succeeded: true,
          verification: 'verified'
        }
      };
      await vi.advanceTimersByTimeAsync(4000);

      expect(observeCalls()).toBe(1);
      expect(invokeCalls.find((call) => call.command === 'cu_broker_observe')?.args).toEqual({ requestId: TURN_ID });
      expect(get(inferenceRequestStore).lifecycle).toBe('completed');
      const assistant = get(chatMessages);
      expect(assistant.find((message) => message.role === 'assistant' && message.requestId === TURN_ID)?.toolCalls?.[0]?.status).toBe('PASS');

      // Terminal state stops the loop: no further observation calls.
      await vi.advanceTimersByTimeAsync(10_000);
      expect(observeCalls()).toBe(1);
    });

    it('keeps polling while pending and Stop revokes the continuation loop', async () => {
      await startTurnWithPendingLaunch();
      observeResponse = { found: true, envelope: launchPendingEnvelope() };

      await vi.advanceTimersByTimeAsync(4000);
      expect(observeCalls()).toBe(1);
      await vi.advanceTimersByTimeAsync(2000);
      expect(observeCalls()).toBe(2);
      expect(get(inferenceRequestStore).lifecycle).toBe('awaiting_verification');

      await cancelLocalModelTurn();
      expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');

      const afterCancel = observeCalls();
      await vi.advanceTimersByTimeAsync(20_000);
      expect(observeCalls()).toBe(afterCancel);
      expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    });

    it('consumes the broker grant once and completes it verified (integration seam)', async () => {
      await startTurnWithPendingLaunch(true);
      observeResponse = {
        found: true,
        envelope: {
          ...launchPendingEnvelope(),
          status: 'completed',
          terminal: true,
          succeeded: true,
          verification: 'verified'
        }
      };
      await vi.advanceTimersByTimeAsync(4000);

      const consume = invokeCalls.find((call) => call.command === 'cu_broker_continuation_consume');
      expect(consume?.args).toEqual({
        grantRef: `cgr_${'d'.repeat(32)}`,
        taskId: `task_${TURN_ID}`,
        stepId: 'step_call_1',
        requestId: TURN_ID,
        actionKind: 'observe',
        input: { action: 'observe' },
        expectedStepIndex: 1
      });
      // The one-time capability is consumed exactly once before completion;
      // the second consume is the B3 replay probe attached to the terminal
      // cleanup revoke, replaying the identical arguments.
      const consumes = invokeCalls.filter((call) => call.command === 'cu_broker_continuation_consume');
      expect(consumes).toHaveLength(2);
      expect(consumes[0]?.args).toEqual(consumes[1]?.args);
      const complete = invokeCalls.find((call) => call.command === 'cu_broker_continuation_complete');
      expect(complete?.args).toMatchObject({ status: 'verified', postconditionVerified: true });
      expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    });

    it('re-arms the grant while pending and revokes it on cancellation', async () => {
      await startTurnWithPendingLaunch(true);
      observeResponse = { found: true, envelope: launchPendingEnvelope() };

      await vi.advanceTimersByTimeAsync(4000);
      const pendingComplete = invokeCalls.find((call) => call.command === 'cu_broker_continuation_complete');
      expect(pendingComplete?.args).toMatchObject({ status: 'pending', postconditionVerified: false });

      await cancelLocalModelTurn();
      expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
      const revoke = invokeCalls.find((call) => call.command === 'cu_broker_continuation_revoke');
      expect(revoke?.args?.grantRef).toBe(`cgr_${'d'.repeat(32)}`);
    });

    it('records typed replay rejection after successful revoke', async () => {
      await startTurnWithPendingLaunch(true);
      observeResponse = { found: true, envelope: launchPendingEnvelope() };

      await vi.advanceTimersByTimeAsync(4000);
      expect(invokeCalls.filter((call) => call.command === 'cu_broker_continuation_consume')).toHaveLength(1);

      await cancelLocalModelTurn();

      // Let the revoke acknowledgement and the replay probe settle (microtasks
      // only; no timers involved in this path).
      for (let i = 0; i < 8; i += 1) {
        await Promise.resolve();
      }

      const consumes = invokeCalls.filter((call) => call.command === 'cu_broker_continuation_consume');
      expect(consumes).toHaveLength(2);
      expect(consumes[0]?.args).toEqual(consumes[1]?.args);
      expect(consumes[1]?.args).toMatchObject({
        grantRef: `cgr_${'d'.repeat(32)}`,
        taskId: `task_${TURN_ID}`,
        stepId: 'step_call_1',
        requestId: TURN_ID,
        actionKind: 'observe',
        input: { action: 'observe' },
        expectedStepIndex: 1
      });

      const trace = (globalThis as { __LOCALCOMET_CONTINUATION_TRACE?: { event: string; request_id?: string; status?: string }[] }).__LOCALCOMET_CONTINUATION_TRACE ?? [];
      expect(trace).toContainEqual({ event: 'continuation_replay_rejected', request_id: TURN_ID, status: 'continuation_replayed' });
      // Raw grant material never leaks into the diagnostic trace.
      expect(JSON.stringify(trace)).not.toContain('cgr_');
      expect(JSON.stringify(trace)).not.toContain('lease_');
    });
  });
});
