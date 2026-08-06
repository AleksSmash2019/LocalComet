import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ModelGatewayPanel from '../src/lib/components/model/ModelGatewayPanel.svelte';
import ManagedRuntimePanel from '../src/lib/components/model/ManagedRuntimePanel.svelte';
import {
  getModelGatewayCatalog,
  listModelGatewayModels,
  probeModelGateway,
  setModelBinding,
  startModelTurn,
  subscribeModelGatewayEvents
} from '../src/lib/bridge/modelGateway';
import {
  applyModelGatewayEvent,
  inferenceRequestStore,
  modelGatewayStore,
  resetModelGatewayStore,
  setGatewayPortText
} from '../src/lib/stores/modelGateway';
import { appendAcceptedChatTurn, resetShellStores } from '../src/lib/stores/shellStore';
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
let listener: ((event: { payload: unknown }) => void) | null = null;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    invokeCalls.push({ command, args });
    if (command === 'request_approval') {
      const tool = (args as { tool: string }).tool;
      const familyMap: Record<string, string> = { 'artifact.download': 'artifact_download', 'artifact.remove': 'artifact_remove', 'runtime.start': 'runtime_start', 'runtime.stop': 'runtime_stop', 'model.binding.set': 'model_binding_set' };
      return { token: `lcap_${'a'.repeat(64)}`, approvalId: `appr_${'b'.repeat(32)}`, callId: `call_${'c'.repeat(32)}`, tool, riskLevel: 'guarded', commandFamily: familyMap[tool] ?? 'model_binding_set', expiresAtUnixMs: Date.now() + 300_000 };
    }
    if (command === 'model_gateway_catalog') return catalogFixture();
    if (command === 'managed_runtime_status') return { engine: 'llama.cpp', state: 'NotInstalled', installation: 'Not installed', runtime_version: null, runtime_instance_id: null, runtime_instance_fingerprint: null, model_id: null, model_display_name: null, binding_fingerprint: null, model_state: 'Unavailable', inference_ready: false, last_error: null };
    if (command === 'managed_runtime_catalog') return { ...TRUST_CATALOG, runtimes: [] };
    if (command === 'managed_model_catalog') return { ...TRUST_CATALOG, engine: 'llama.cpp', model_root: '<MANAGED_MODEL_ROOT>', models: [], maximum_models: 32 };
    if (command === 'managed_installed_artifacts') return { ...TRUST_CATALOG, artifacts: [] };
    if (command === 'managed_runtime_logs') return { stdout_tail: [], stderr_tail: [] };
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
  beforeEach(() => {
    resetModelGatewayStore();
    resetShellStores();
    installTauriMock();
  });

  it('uses exactly the fixed model gateway commands', async () => {
    await getModelGatewayCatalog();
    await probeModelGateway(1234);
    await listModelGatewayModels(1234);
    await setModelBinding({ providerId: 'openai-compatible-local', harnessId: 'minimal', port: 1234, modelId: 'local-model' });
    await startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', locale: 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false } });
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
      'fileIds',
      'locale',
      'maxTokens',
      'messages',
      'modelId',
      'prompt',
      'requestId',
      'submittedAtUnixMs'
    ]);
  });

  it('passes only validated opaque file identities to the model command', async () => {
    const fileId = 'd'.repeat(64);
    const response = await startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', fileIds: [fileId], locale: 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false } });
    expect(invokeCalls.at(-1)?.args?.fileIds).toEqual([fileId]);
    expect(response.file_context).toMatchObject({ included_bytes: 5, truncated: true });
    await expect(startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', fileIds: ['C:\\temp\\notes.md'], locale: 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false } })).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(1);
  });

  it('rejects invalid ports before invoking Tauri', async () => {
    await expect(probeModelGateway(80)).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);
    setGatewayPortText('12x34');
    expect(get(modelGatewayStore).portText).toBe('1234');
  });

  it('rejects an unsupported assistant locale before invoking Tauri', async () => {
    await expect(startModelTurn({ requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, maxTokens: 256, prompt: 'hello', locale: 'fr' as 'ru', bindingFingerprint: FINGERPRINT, agentPermissions: { files: false, shell: false, computerUse: false, tools: false, internet: false } })).rejects.toMatchObject({ code: 'invalid_payload' });
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
    inferenceRequestStore.set({ lifecycle: 'accepted', requestId: TURN_ID, chatSessionId: 'local-chat', modelId: 'local-model', submittedAtUnixMs: 1, acceptedAtUnixMs: 1, firstTokenAtUnixMs: null, terminalAtUnixMs: null, maxTokens: 256, chunkCount: 0, nextSequence: 0, receivedContent: false, cancellationAccepted: false, terminalMethod: null, rejectedEventCount: 0, lastError: null });
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
    expect(body).toContain('OpenAI-compatible local');
    expect(body).toContain('127.0.0.1');
    expect(body).not.toMatch(/URL|API key|Headers|Temperature|Attachments|Tool controls/i);
  });

  it('renders managed runtime without URL, port, API-key, executable or path controls', () => {
    const body = render(ManagedRuntimePanel).body;
    expect(body).toContain('Managed llama.cpp');
    expect(body).toContain('Not installed');
    expect(body).not.toMatch(/URL|Port|API key|Executable|Model path|Environment|Arguments/i);
  });
});
