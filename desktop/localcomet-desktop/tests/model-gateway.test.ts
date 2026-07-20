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
  modelGatewayStore,
  resetModelGatewayStore,
  setGatewayPortText
} from '../src/lib/stores/modelGateway';
import type { ModelGatewayEvent } from '../src/lib/types/modelGateway';

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
    if (command === 'model_gateway_catalog') return catalogFixture();
    if (command === 'managed_runtime_status') return { engine: 'llama.cpp', state: 'NotInstalled', installation: 'Not installed', runtime_version: null, runtime_instance_id: null, runtime_instance_fingerprint: null, model_id: null, model_display_name: null, binding_fingerprint: null, last_error: null };
    if (command === 'managed_runtime_catalog') return { ...TRUST_CATALOG, runtimes: [] };
    if (command === 'managed_model_catalog') return { ...TRUST_CATALOG, engine: 'llama.cpp', model_root: '<MANAGED_MODEL_ROOT>', models: [], maximum_models: 32 };
    if (command === 'managed_installed_artifacts') return { ...TRUST_CATALOG, artifacts: [] };
    if (command === 'managed_runtime_logs') return { stdout_tail: [], stderr_tail: [] };
    if (command === 'model_gateway_probe') return { status: 'Ready', provider_id: 'openai-compatible-local', host: '127.0.0.1', port: args?.port, base_path: '/v1', model_count: 1 };
    if (command === 'model_gateway_list_models') return { provider_id: 'openai-compatible-local', host: '127.0.0.1', port: args?.port, models: [{ model_id: 'local-model' }], discovered_fingerprint: FINGERPRINT };
    if (command === 'model_binding_set') return { provider_id: 'openai-compatible-local', harness_id: args?.harnessId, host: '127.0.0.1', port: args?.port, base_path: '/v1', model_id: args?.modelId, binding_fingerprint: FINGERPRINT, discovered_fingerprint: FINGERPRINT, persistence: false };
    if (command === 'model_turn_start') return { turn_id: TURN_ID, state: 'GENERATING', provider_id: 'openai-compatible-local', harness_id: 'minimal', model_id: 'local-model', binding_fingerprint: FINGERPRINT, model_called: false, tools_executed: 0, persistence: false };
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
  return {
    method,
    sequence,
    reply_to: TURN_ID,
    turn_id: TURN_ID,
    state: patch.state ?? 'Generating',
    text: patch.text ?? null,
    model_called: patch.model_called ?? true,
    tools_executed: 0,
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
    installTauriMock();
  });

  it('uses exactly the fixed model gateway commands', async () => {
    await getModelGatewayCatalog();
    await probeModelGateway(1234);
    await listModelGatewayModels(1234);
    await setModelBinding({ providerId: 'openai-compatible-local', harnessId: 'minimal', port: 1234, modelId: 'local-model' });
    await startModelTurn('hello', FINGERPRINT);
    expect(invokeCalls.map((call) => call.command)).toEqual([
      'model_gateway_catalog',
      'model_gateway_probe',
      'model_gateway_list_models',
      'model_binding_set',
      'model_turn_start'
    ]);
    expect(JSON.stringify(invokeCalls)).not.toContain('http://');
    expect(JSON.stringify(invokeCalls)).not.toContain('api');
  });

  it('rejects invalid ports before invoking Tauri', async () => {
    await expect(probeModelGateway(80)).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(invokeCalls).toHaveLength(0);
    setGatewayPortText('12x34');
    expect(get(modelGatewayStore).portText).toBe('1234');
  });

  it('subscribes to model events and updates truthful telemetry', async () => {
    const seen: string[] = [];
    await subscribeModelGatewayEvents((event) => seen.push(event.method));
    listener?.({ payload: { method: 'model.output.delta', sequence: 1, reply_to: TURN_ID, turn_id: TURN_ID, state: 'Generating', text: 'hi', metadata: { model_called: true, tools_executed: 0, persistence: false, provider_id: 'openai-compatible-local', harness_id: 'minimal', model_id: 'local-model', binding_fingerprint: FINGERPRINT } } });
    expect(seen).toEqual(['model.output.delta']);
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
