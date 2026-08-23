import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn()
}));

import {
  canAcceptToolCallback,
  inferenceRequestStore,
  isInferenceTerminal,
  resetModelGatewayStore
} from '../src/lib/stores/modelGateway';

function setRequest(requestId: string, lifecycle: 'accepted' | 'cancelling' | 'awaiting_verification' | 'completed'): void {
  inferenceRequestStore.set({
    lifecycle,
    requestId,
    chatSessionId: 'default',
    modelId: 'pinned-qwen3',
    effort: 'off',
    submittedAtUnixMs: 1,
    acceptedAtUnixMs: 2,
    firstTokenAtUnixMs: null,
    terminalAtUnixMs: null,
    maxTokens: 4096,
    chunkCount: 0,
    nextSequence: 0,
    receivedContent: true,
    cancellationAccepted: lifecycle === 'cancelling',
    terminalMethod: null,
    rejectedEventCount: 0,
    lastError: null
  });
}

describe('model request lifecycle correlation', () => {
  beforeEach(() => resetModelGatewayStore());

  it('accepts a callback only for the current accepted request', () => {
    setRequest('request-a', 'accepted');

    expect(canAcceptToolCallback('request-a')).toBe(true);
    expect(canAcceptToolCallback('request-b')).toBe(false);
  });

  it('rejects a late callback after Stop moved the request to cancelling', () => {
    setRequest('request-a', 'cancelling');

    expect(canAcceptToolCallback('request-a')).toBe(false);
  });

  it('rejects a late callback after a new turn superseded the request', () => {
    setRequest('request-a', 'accepted');
    setRequest('request-b', 'accepted');

    expect(canAcceptToolCallback('request-a')).toBe(false);
    expect(canAcceptToolCallback('request-b')).toBe(true);
  });

  it('keeps awaiting_verification transient for the broker continuation but closed to direct tool callbacks', () => {
    setRequest('request-a', 'awaiting_verification');

    expect(isInferenceTerminal('awaiting_verification')).toBe(false);
    expect(canAcceptToolCallback('request-a')).toBe(false);
  });

  it('rejects callbacks after authoritative completion', () => {
    setRequest('request-a', 'completed');

    expect(isInferenceTerminal(get(inferenceRequestStore).lifecycle)).toBe(true);
    expect(canAcceptToolCallback('request-a')).toBe(false);
  });
});
