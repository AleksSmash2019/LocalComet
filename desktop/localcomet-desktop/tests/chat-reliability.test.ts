import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  INFERENCE_TIMEOUTS_MS,
  applyModelGatewayEvent,
  cancelLocalModelTurn,
  inferenceRequestStore,
  managedModelReady,
  managedRuntimeStore,
  modelGatewayStore,
  resetModelGatewayStore,
  shutdownModelGateway,
  startLocalModelTurn
} from '../src/lib/stores/modelGateway';
import {
  chatMessages,
  composerDraft,
  resetShellStores,
  setComposerDraft
} from '../src/lib/stores/shellStore';
import type { ModelGatewayEvent } from '../src/lib/types/modelGateway';

const MODEL_ID = 'qwen2.5-1.5b-instruct-q4-k-m';
const RUNTIME_ID = 'llama-cpp-windows-x86-64-cpu-bootstrap';
const RUNTIME_INSTANCE_ID = 'd'.repeat(32);
const FINGERPRINT = 'b'.repeat(64);
const ATTACH_FINGERPRINT = 'f'.repeat(64);
const CATALOG_DIGEST = 'c'.repeat(64);

let listener: ((event: { payload: unknown }) => void) | null = null;
let listenCount = 0;
let cleanupCount = 0;
let invocationOrder: string[] = [];
let invokeCalls: { command: string; args?: Record<string, unknown> }[] = [];
let startHandler: (args: Record<string, unknown>) => Promise<unknown>;
let cancelHandler: (args: Record<string, unknown>) => Promise<unknown>;
let managedStatusHandler: () => Promise<unknown>;
let bindingHandler: (args: Record<string, unknown>) => Promise<unknown>;

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_channel: string, callback: (event: { payload: unknown }) => void) => {
    invocationOrder.push('listen');
    listenCount += 1;
    listener = callback;
    return () => {
      cleanupCount += 1;
      listener = null;
    };
  })
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>) => {
    invocationOrder.push(command);
    invokeCalls.push({ command, args });
    if (command === 'model_turn_start') return startHandler(args ?? {});
    if (command === 'model_turn_cancel') return cancelHandler(args ?? {});
    if (command === 'managed_runtime_status') return managedStatusHandler();
    if (command === 'model_binding_set') return bindingHandler(args ?? {});
    throw { code: 'unexpected_command', message: command };
  })
}));

function acceptance(args: Record<string, unknown>) {
  return {
    request_id: args.requestId,
    chat_session_id: args.chatSessionId,
    turn_id: args.requestId,
    state: 'Accepted',
    model_id: args.modelId,
    submitted_at_unix_ms: args.submittedAtUnixMs,
    max_tokens: args.maxTokens,
    binding_fingerprint: args.bindingFingerprint
  };
}

function cancellation(args: Record<string, unknown>, patch: Record<string, unknown> = {}) {
  return {
    request_id: args.requestId,
    turn_id: args.requestId,
    state: 'Cancelling',
    accepted: true,
    already_terminal: false,
    worker_alive: true,
    ...patch
  };
}

function seedReadyManagedModel(): void {
  const binding = {
    provider_id: 'managed-llama-cpp' as const,
    harness_id: 'minimal' as const,
    model_id: MODEL_ID,
    binding_fingerprint: FINGERPRINT,
    discovered_fingerprint: 'a'.repeat(64),
    persistence: false as const,
    runtime_instance_id: RUNTIME_INSTANCE_ID
  };
  managedRuntimeStore.set({
    status: {
      engine: 'llama.cpp',
      state: 'Ready',
      installation: 'Installed',
      runtime_version: 'b10068',
      runtime_instance_id: RUNTIME_INSTANCE_ID,
      runtime_instance_fingerprint: 'e'.repeat(64),
      model_id: MODEL_ID,
      model_display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      binding_fingerprint: ATTACH_FINGERPRINT,
      model_state: 'Ready',
      inference_ready: true,
      last_error: null
    },
    catalogIdentity: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST },
    runtimeCatalog: [],
    catalog: [{
      model_id: MODEL_ID,
      provider: 'Qwen',
      family: 'Qwen2.5',
      display_name: 'Qwen2.5 1.5B Instruct Q4_K_M',
      format: 'GGUF',
      quantization: 'Q4_K_M',
      upstream_repository: 'https://example.invalid/model',
      upstream_revision: 'revision',
      asset_filename: 'model.gguf',
      asset_bytes: 2,
      asset_sha256: '2'.repeat(64),
      license_id: 'apache-2.0',
      compatible_runtime_ids: [RUNTIME_ID],
      public_distribution: false,
      installer_bundled: false,
      bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION',
      status: 'approved_internal_bootstrap'
    }],
    installedArtifacts: [
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: RUNTIME_ID, kind: 'runtime', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 1, expected_sha256: '1'.repeat(64), observed_bytes: null, observed_sha256: null, validation_code: 'valid', verified_unix_ms: 1 },
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: MODEL_ID, kind: 'model', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 2, expected_sha256: '2'.repeat(64), observed_bytes: 2, observed_sha256: '2'.repeat(64), validation_code: 'valid', verified_unix_ms: 1 }
    ],
    readiness: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, model_id: MODEL_ID, model_status: 'valid', compatible_runtime_ids: [RUNTIME_ID], selected_runtime_id: RUNTIME_ID, runtime_status: 'valid', compatibility: 'compatible', readiness: 'ready', launchable: true },
    selectedModelId: MODEL_ID,
    harnessId: 'minimal',
    binding,
    logs: { stdout_tail: [], stderr_tail: [] },
    lastError: null
  });
  modelGatewayStore.update((state) => ({ ...state, binding, status: 'Bound', lastError: null }));
}

function event(method: ModelGatewayEvent['method'], sequence: number, text: string | null = null, patch: Partial<ModelGatewayEvent> = {}): ModelGatewayEvent {
  const request = get(inferenceRequestStore);
  const stateByMethod = {
    'model.turn.started': 'Streaming',
    'model.output.delta': 'Streaming',
    'model.turn.completed': 'Completed',
    'model.turn.cancelled': 'Cancelled',
    'model.turn.timed_out': 'TimedOut',
    'model.turn.failed': 'Failed'
  } as const;
  return {
    method,
    sequence,
    reply_to: request.requestId!,
    request_id: request.requestId!,
    chat_session_id: request.chatSessionId!,
    turn_id: request.requestId!,
    state: stateByMethod[method],
    text,
    model_called: true,
    tools_executed: 0,
    persistence: false,
    generated_bytes: text?.length ?? 0,
    provider_id: 'managed-llama-cpp',
    harness_id: 'minimal',
    model_id: request.modelId!,
    binding_fingerprint: FINGERPRINT,
    ...patch
  };
}

async function startAccepted(prompt = 'hello'): Promise<string> {
  setComposerDraft(prompt);
  expect(await startLocalModelTurn(prompt, 'local-chat')).toBe(true);
  return get(inferenceRequestStore).requestId!;
}

beforeEach(() => {
  vi.useRealTimers();
  resetModelGatewayStore();
  resetShellStores();
  listener = null;
  listenCount = 0;
  cleanupCount = 0;
  invocationOrder = [];
  invokeCalls = [];
  startHandler = async (args) => acceptance(args);
  cancelHandler = async (args) => cancellation(args);
  seedReadyManagedModel();
  managedStatusHandler = async () => get(managedRuntimeStore).status;
  bindingHandler = async () => get(managedRuntimeStore).binding;
});

afterEach(() => {
  resetModelGatewayStore();
  resetShellStores();
  vi.useRealTimers();
});

describe('typed real-model chat lifecycle', () => {
  it('derives truthful readiness and never generates without it', async () => {
    expect(get(managedRuntimeStore).status?.binding_fingerprint).not.toBe(get(managedRuntimeStore).binding?.binding_fingerprint);
    expect(get(managedModelReady)).toBe(true);
    managedRuntimeStore.update((state) => ({ ...state, status: state.status ? { ...state.status, inference_ready: false } : null }));
    expect(get(managedModelReady)).toBe(false);
    setComposerDraft('keep this draft');
    expect(await startLocalModelTurn('keep this draft', 'local-chat')).toBe(false);
    expect(invokeCalls).toHaveLength(0);
    expect(get(composerDraft)).toBe('keep this draft');
    expect(get(chatMessages)).toHaveLength(0);
  });

  it('registers the listener before submit and sends the fixed typed request', async () => {
    await startAccepted();
    expect(invocationOrder).toEqual(['listen', 'managed_runtime_status', 'model_binding_set', 'model_turn_start']);
    const args = invokeCalls.find((call) => call.command === 'model_turn_start')?.args ?? {};
    expect(args.requestId).toMatch(/^[0-9a-f]{24}$/);
    expect(args).toMatchObject({ chatSessionId: 'local-chat', modelId: MODEL_ID, maxTokens: 256, prompt: 'hello', bindingFingerprint: FINGERPRINT });
    expect(get(composerDraft)).toBe('');
    expect(get(chatMessages).map((message) => message.role)).toEqual(['user', 'assistant']);
  });

  it('invalidates a stale binding before submission when the runtime has exited', async () => {
    managedStatusHandler = async () => ({
      ...get(managedRuntimeStore).status,
      state: 'Failed',
      model_state: 'Failed',
      inference_ready: false,
      last_error: 'managed runtime exited'
    });
    expect(await startLocalModelTurn('must not submit', 'local-chat')).toBe(false);
    expect(invokeCalls.some((call) => call.command === 'model_turn_start')).toBe(false);
    expect(get(managedModelReady)).toBe(false);
    expect(get(chatMessages)).toHaveLength(0);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'idle', lastError: { code: 'runtime_unavailable' } });
  });

  it('claims the submission gate before asynchronous preflight', async () => {
    let resolveStatus!: (value: unknown) => void;
    managedStatusHandler = () => new Promise((resolve) => {
      resolveStatus = resolve;
    });
    const first = startLocalModelTurn('first concurrent prompt', 'local-chat');
    await vi.waitFor(() => expect(invokeCalls.some((call) => call.command === 'managed_runtime_status')).toBe(true));
    expect(await startLocalModelTurn('second concurrent prompt', 'local-chat')).toBe(false);
    resolveStatus(get(managedRuntimeStore).status);
    expect(await first).toBe(true);
    expect(invokeCalls.filter((call) => call.command === 'model_turn_start')).toHaveLength(1);
  });

  it('buffers ordered events that arrive before acceptance and renders one assistant', async () => {
    let resolveStart!: (value: unknown) => void;
    startHandler = (args) => new Promise((resolve) => {
      resolveStart = () => resolve(acceptance(args));
    });
    setComposerDraft('race');
    const started = startLocalModelTurn('race', 'local-chat');
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('submitted'));
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'real '));
    applyModelGatewayEvent(event('model.output.delta', 2, 'answer'));
    applyModelGatewayEvent(event('model.turn.completed', 3));
    resolveStart(undefined);
    expect(await started).toBe(true);
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    expect(get(inferenceRequestStore)).toMatchObject({ chunkCount: 2 });
    expect(get(inferenceRequestStore).firstTokenAtUnixMs).not.toBeNull();
    expect(get(inferenceRequestStore).terminalAtUnixMs).not.toBeNull();
    expect(get(chatMessages).filter((message) => message.role === 'assistant')).toEqual([
      expect.objectContaining({ body: 'real answer', state: 'completed' })
    ]);
  });

  it('ignores foreign IDs and fails closed on a sequence gap', async () => {
    await startAccepted();
    const before = get(inferenceRequestStore);
    applyModelGatewayEvent(event('model.turn.started', 0, null, { request_id: 'f'.repeat(24), turn_id: 'f'.repeat(24), reply_to: 'f'.repeat(24) }));
    expect(get(inferenceRequestStore)).toEqual(before);
    applyModelGatewayEvent(event('model.output.delta', 1, 'gap'));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });
    expect(get(chatMessages).at(-1)).toMatchObject({ role: 'assistant', body: '', state: 'failed' });
  });

  it('rejects mismatched acceptance and event binding fingerprints', async () => {
    startHandler = async (args) => ({ ...acceptance(args), binding_fingerprint: '0'.repeat(64) });
    expect(await startLocalModelTurn('bad acceptance', 'local-chat')).toBe(false);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'invalid_payload' } });
    expect(get(chatMessages)).toHaveLength(0);

    startHandler = async (args) => acceptance(args);
    await startAccepted('bad event');
    applyModelGatewayEvent(event('model.turn.started', 0, null, { binding_fingerprint: '0'.repeat(64) }));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });
    expect(get(chatMessages).at(-1)).toMatchObject({ role: 'assistant', body: '', state: 'failed' });
    await vi.waitFor(() => expect(invokeCalls.filter((call) => call.command === 'model_turn_cancel')).toHaveLength(1));
  });

  it('rejects event provider and harness telemetry outside the active binding', async () => {
    await startAccepted('bad provider');
    applyModelGatewayEvent(event('model.turn.started', 0, null, { provider_id: 'openai-compatible-local' }));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });

    resetModelGatewayStore();
    resetShellStores();
    seedReadyManagedModel();
    await startAccepted('bad harness');
    applyModelGatewayEvent(event('model.turn.started', 0, null, { harness_id: 'native-localcomet' }));
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'protocol_mismatch' } });
  });

  it('rejects duplicate terminals and late tokens without changing finalized content', async () => {
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'done'));
    applyModelGatewayEvent(event('model.turn.completed', 2));
    const finalized = get(chatMessages);
    applyModelGatewayEvent(event('model.turn.completed', 3));
    applyModelGatewayEvent(event('model.output.delta', 4, ' late'));
    expect(get(chatMessages)).toEqual(finalized);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'completed', rejectedEventCount: 2 });
  });

  it('gives accepted cancellation precedence and ignores completion/late content', async () => {
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'partial'));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'cancelling', cancellationAccepted: true });
    applyModelGatewayEvent(event('model.turn.completed', 2));
    applyModelGatewayEvent(event('model.output.delta', 3, ' late'));
    applyModelGatewayEvent(event('model.turn.failed', 4, null, { error: { code: 'late_failure', message: 'late', retryable: false } }));
    applyModelGatewayEvent(event('model.turn.timed_out', 5, null, { error: { code: 'request_timed_out', message: 'late', retryable: true } }));
    applyModelGatewayEvent(event('model.turn.cancelled', 6));
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    expect(get(chatMessages).at(-1)).toMatchObject({ body: 'partial', state: 'cancelled' });
    expect(get(inferenceRequestStore).rejectedEventCount).toBe(3);
  });

  it('projects an accepted turn when Stop is pressed before acceptance resolves', async () => {
    let resolveStart!: (value?: unknown) => void;
    startHandler = (args) => new Promise((resolve) => {
      resolveStart = () => resolve(acceptance(args));
    });
    const pendingStart = startLocalModelTurn('cancel immediately', 'local-chat');
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('submitted'));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelling');

    resolveStart();
    expect(await pendingStart).toBe(true);
    expect(get(chatMessages).map((message) => message.role)).toEqual(['user', 'assistant']);
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelling');
    applyModelGatewayEvent(event('model.turn.cancelled', 0));
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    expect(get(chatMessages).at(-1)).toMatchObject({ body: '', state: 'cancelled' });
    expect(get(composerDraft)).toBe('');
  });

  it('settles cancellation when an unaccepted start rejects late', async () => {
    let rejectStart!: (reason?: unknown) => void;
    startHandler = () => new Promise((_resolve, reject) => {
      rejectStart = reject;
    });
    const pendingStart = startLocalModelTurn('cancel race', 'local-chat');
    await vi.waitFor(() => expect(get(inferenceRequestStore).lifecycle).toBe('submitted'));
    await cancelLocalModelTurn();
    rejectStart({ code: 'request_not_found', message: 'late start response race' });
    expect(await pendingStart).toBe(false);
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    applyModelGatewayEvent(event('model.turn.cancelled', 0));
    expect(get(inferenceRequestStore).lifecycle).toBe('cancelled');
    expect(get(chatMessages)).toHaveLength(0);
  });

  it('awaits the authoritative terminal when cancellation loses the terminal race', async () => {
    cancelHandler = async (args) => cancellation(args, { state: 'Cancelled', accepted: false, already_terminal: true, worker_alive: false });
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'won the race'));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'cancelling', cancellationAccepted: false });
    applyModelGatewayEvent(event('model.turn.completed', 2));
    expect(get(inferenceRequestStore).lifecycle).toBe('completed');
    expect(get(chatMessages).at(-1)).toMatchObject({ body: 'won the race', state: 'completed' });
  });

  it('fails closed on an incoherent cancellation acknowledgement', async () => {
    cancelHandler = async (args) => cancellation(args, { state: 'Cancelled', accepted: true, already_terminal: false, worker_alive: true });
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    await cancelLocalModelTurn();
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'failed', lastError: { code: 'invalid_payload' } });
  });

  it('bounds acceptance, first-token and inactivity waits and remains retryable', async () => {
    vi.useFakeTimers();
    let resolveLate!: (value: unknown) => void;
    startHandler = (args) => new Promise((resolve) => {
      resolveLate = () => resolve(acceptance(args));
    });
    setComposerDraft('retry me');
    const pending = startLocalModelTurn('retry me', 'local-chat');
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.acceptance);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'request_acceptance_timeout' } });
    expect(get(composerDraft)).toBe('retry me');
    resolveLate(undefined);
    expect(await pending).toBe(false);

    startHandler = async (args) => acceptance(args);
    expect(await startLocalModelTurn('retry me', 'local-chat')).toBe(true);
    applyModelGatewayEvent(event('model.turn.started', 0));
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.firstToken);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'first_token_timeout' } });

    expect(await startLocalModelTurn('third', 'local-chat')).toBe(true);
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'partial'));
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.inactivity);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'stream_inactivity_timeout' } });
    expect(get(chatMessages).at(-1)).toMatchObject({ body: 'partial', state: 'timed_out' });
  });

  it('keeps second requests isolated and cleans/re-registers the listener', async () => {
    const firstId = await startAccepted('first');
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'one'));
    applyModelGatewayEvent(event('model.turn.completed', 2));
    shutdownModelGateway();
    expect(cleanupCount).toBe(1);

    const secondId = await startAccepted('second');
    expect(secondId).not.toBe(firstId);
    expect(listenCount).toBe(2);
    applyModelGatewayEvent(event('model.turn.started', 0));
    applyModelGatewayEvent(event('model.output.delta', 1, 'two'));
    applyModelGatewayEvent(event('model.turn.completed', 2));
    applyModelGatewayEvent(event('model.output.delta', 3, 'old', { request_id: firstId, turn_id: firstId, reply_to: firstId }));
    expect(get(chatMessages).filter((message) => message.role === 'assistant').map((message) => message.body)).toEqual(['one', 'two']);
  });

  it('turns cancel acknowledgement timeout into one stable terminal', async () => {
    vi.useFakeTimers();
    cancelHandler = async () => new Promise(() => undefined);
    await startAccepted();
    applyModelGatewayEvent(event('model.turn.started', 0));
    const cancelling = cancelLocalModelTurn();
    await vi.advanceTimersByTimeAsync(INFERENCE_TIMEOUTS_MS.cancelAcknowledgement);
    expect(get(inferenceRequestStore)).toMatchObject({ lifecycle: 'timed_out', lastError: { code: 'cancel_ack_timeout' } });
    void cancelling;
  });
});
