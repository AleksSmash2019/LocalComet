import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import { clearQueuedTurn, dequeueTurn, queuedTurnStore, queueTurn } from '../src/lib/stores/turnQueue';

describe('turnQueue (single-slot send queue)', () => {
  beforeEach(() => {
    clearQueuedTurn();
  });

  it('queues a trimmed draft with its conversation and files', () => {
    expect(queueTurn('chat-1', '  привет  ', ['f1'])).toBe(true);
    const queued = get(queuedTurnStore);
    expect(queued).toEqual({ conversationId: 'chat-1', draft: 'привет', fileIds: ['f1'] });
  });

  it('refuses empty drafts', () => {
    expect(queueTurn('chat-1', '   ')).toBe(false);
    expect(get(queuedTurnStore)).toBeNull();
  });

  it('replaces the previous slot (single slot semantics)', () => {
    queueTurn('chat-1', 'first');
    queueTurn('chat-2', 'second');
    const queued = dequeueTurn();
    expect(queued?.draft).toBe('second');
    expect(queued?.conversationId).toBe('chat-2');
  });

  it('dequeue clears the slot', () => {
    queueTurn('chat-1', 'hello');
    expect(dequeueTurn()).not.toBeNull();
    expect(get(queuedTurnStore)).toBeNull();
    expect(dequeueTurn()).toBeNull();
  });
});
