import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import {
  appendAssistantChunk,
  chatMessages,
  finalizeAssistantMessage,
  appendAcceptedChatTurn,
  resetShellStores
} from '../src/lib/stores/shellStore';
import { conversationStore, createConversation, selectConversation, DEFAULT_CONVERSATION_ID } from '../src/lib/stores/conversationStore';
import { CHAT_HISTORY_KEY, clearChatHistory, loadChatHistory } from '../src/lib/stores/chatHistory';

const REQUEST_ID = 'a'.repeat(24);

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => { values.delete(key); },
    setItem: (key: string, value: string) => { values.set(key, value); }
  };
}

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: createMemoryStorage()
});

describe('chat history persistence', () => {
  beforeEach(() => {
    localStorage.clear();
    resetShellStores();
  });

  afterEach(() => {
    clearChatHistory();
  });

  it('persists a completed turn and restores it on reset', async () => {
    expect(appendAcceptedChatTurn(REQUEST_ID, 'привет как дела', DEFAULT_CONVERSATION_ID)).toBe(true);
    appendAssistantChunk(REQUEST_ID, 'отлично, работаю');
    expect(finalizeAssistantMessage(REQUEST_ID, 'completed')).toBe(true);

    // The save is coalesced on a 500ms timer; flush it.
    await new Promise((resolve) => setTimeout(resolve, 700));

    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    expect(raw).toBeTruthy();
    const record = JSON.parse(raw ?? '{}');
    expect(record.version).toBe(1);
    expect(record.messages).toHaveLength(2);

    // A fresh app session: reset restores the finished conversation.
    resetShellStores();
    const messages = get(chatMessages);
    expect(messages).toHaveLength(2);
    expect(messages[0].role).toBe('user');
    expect(messages[0].body).toBe('привет как дела');
    expect(messages[1].body).toBe('отлично, работаю');
    expect(messages[1].state).toBe('completed');
    expect(get(conversationStore).activeId).toBe(DEFAULT_CONVERSATION_ID);
  });

  it('never persists in-flight assistant turns', async () => {
    appendAcceptedChatTurn(REQUEST_ID, 'вопрос', DEFAULT_CONVERSATION_ID);
    appendAssistantChunk(REQUEST_ID, 'частичный');
    // No terminal finalize: the assistant state stays 'streaming'.
    await new Promise((resolve) => setTimeout(resolve, 700));

    resetShellStores();
    const messages = get(chatMessages);
    // The user message survives; the in-flight assistant half does not.
    expect(messages.some((message) => message.role === 'assistant' && message.requestId === REQUEST_ID)).toBe(false);
    expect(messages.some((message) => message.role === 'user' && message.body === 'вопрос')).toBe(true);
  });

  it('restores multiple conversations and keeps the active one', async () => {
    const second = createConversation();
    expect(appendAcceptedChatTurn(REQUEST_ID, 'второй чат', second)).toBe(true);
    expect(finalizeAssistantMessage(REQUEST_ID, 'completed')).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 700));

    resetShellStores();
    const state = get(conversationStore);
    expect(state.conversations.map((c) => c.id)).toContain(second);
    expect(state.activeId).toBe(second);
    expect(get(chatMessages).some((message) => message.body === 'второй чат')).toBe(true);

    // Switching back to the default conversation keeps its messages gone
    // (that conversation has none), and selecting again is safe.
    selectConversation(DEFAULT_CONVERSATION_ID);
    expect(get(conversationStore).activeId).toBe(DEFAULT_CONVERSATION_ID);
  });

  it('loadChatHistory rejects malformed records', () => {
    localStorage.setItem(CHAT_HISTORY_KEY, 'not-json{');
    expect(loadChatHistory().messages).toHaveLength(0);
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify({ version: 99, messages: [] }));
    expect(loadChatHistory().messages).toHaveLength(0);
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify({ version: 1, messages: [{ id: 'x', role: 'assistant', body: 'no requestId' }] }));
    expect(loadChatHistory().messages).toHaveLength(0);
  });
});
