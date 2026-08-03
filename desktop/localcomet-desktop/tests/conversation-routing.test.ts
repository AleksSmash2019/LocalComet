import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import {
  appendAcceptedChatTurn,
  appendAssistantChunk,
  chatMessages,
  resetShellStores
} from '../src/lib/stores/shellStore';
import {
  conversationStore,
  createConversation,
  DEFAULT_CONVERSATION_ID
} from '../src/lib/stores/conversationStore';

describe('conversation stream routing (ADR-014 ОБЯЗ-1)', () => {
  beforeEach(() => {
    resetShellStores();
  });

  it('routes stream chunks to the request conversation, not the active one', () => {
    const conversationA = DEFAULT_CONVERSATION_ID;
    const requestId = 'a'.repeat(24);
    expect(appendAcceptedChatTurn(requestId, 'запрос в A', conversationA)).toBe(true);

    const conversationB = createConversation();
    expect(get(conversationStore).activeId).toBe(conversationB);

    expect(appendAssistantChunk(requestId, ' ответ')).toBe(true);

    const all = get(chatMessages);
    const messagesA = all.filter((m) => m.conversationId === conversationA);
    const messagesB = all.filter((m) => m.conversationId === conversationB);

    const assistantA = messagesA.find((m) => m.role === 'assistant' && m.requestId === requestId);
    expect(assistantA?.body).toBe(' ответ');
    expect(messagesB).toHaveLength(0);
  });

  it('keeps each conversation history isolated when interleaving turns', () => {
    const conversationA = DEFAULT_CONVERSATION_ID;
    const conversationB = createConversation();

    const requestA = 'a'.repeat(24);
    const requestB = 'b'.repeat(24);
    expect(appendAcceptedChatTurn(requestA, 'первый', conversationA)).toBe(true);
    expect(appendAcceptedChatTurn(requestB, 'второй', conversationB)).toBe(true);

    expect(appendAssistantChunk(requestA, ' ответ A')).toBe(true);
    expect(appendAssistantChunk(requestB, ' ответ B')).toBe(true);

    const all = get(chatMessages);
    const bodiesA = all.filter((m) => m.conversationId === conversationA).map((m) => m.body);
    const bodiesB = all.filter((m) => m.conversationId === conversationB).map((m) => m.body);

    expect(bodiesA).toContain(' ответ A');
    expect(bodiesA).not.toContain(' ответ B');
    expect(bodiesB).toContain(' ответ B');
    expect(bodiesB).not.toContain(' ответ A');
  });
});
