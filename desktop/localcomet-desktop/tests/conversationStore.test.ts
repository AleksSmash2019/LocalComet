import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import {
  activeConversation,
  applyAutoTitle,
  conversationStore,
  createConversation,
  DEFAULT_CONVERSATION_ID,
  getActiveConversationId,
  NEW_CHAT_TITLE,
  renameConversation,
  resetConversationStore,
  selectConversation
} from '$lib/stores/conversationStore';

const CHAT_SESSION_ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;

describe('conversationStore', () => {
  beforeEach(() => {
    resetConversationStore();
  });

  it('starts with a single default conversation active', () => {
    const state = get(conversationStore);
    expect(state.conversations).toHaveLength(1);
    expect(state.conversations[0].id).toBe(DEFAULT_CONVERSATION_ID);
    expect(state.conversations[0].title).toBe(NEW_CHAT_TITLE);
    expect(state.activeId).toBe(DEFAULT_CONVERSATION_ID);
    expect(get(activeConversation)?.id).toBe(DEFAULT_CONVERSATION_ID);
  });

  it('createConversation adds a conversation with a valid chatSessionId and activates it', () => {
    const id = createConversation();
    expect(id).toMatch(CHAT_SESSION_ID_RE);
    const state = get(conversationStore);
    expect(state.conversations).toHaveLength(2);
    expect(state.conversations[0].id).toBe(id);
    expect(state.conversations[0].title).toBe(NEW_CHAT_TITLE);
    expect(state.activeId).toBe(id);
  });

  it('createConversation generates unique ids', () => {
    const a = createConversation();
    const b = createConversation();
    expect(a).not.toBe(b);
    expect(a).toMatch(CHAT_SESSION_ID_RE);
    expect(b).toMatch(CHAT_SESSION_ID_RE);
  });

  it('selectConversation switches the active conversation', () => {
    const id = createConversation();
    selectConversation(DEFAULT_CONVERSATION_ID);
    expect(get(conversationStore).activeId).toBe(DEFAULT_CONVERSATION_ID);
    selectConversation(id);
    expect(get(conversationStore).activeId).toBe(id);
  });

  it('selectConversation ignores an unknown id', () => {
    selectConversation('does-not-exist');
    expect(get(conversationStore).activeId).toBe(DEFAULT_CONVERSATION_ID);
  });

  it('renameConversation updates the title', () => {
    renameConversation(DEFAULT_CONVERSATION_ID, 'Мой чат');
    expect(get(conversationStore).conversations[0].title).toBe('Мой чат');
  });

  it('renameConversation ignores an empty title', () => {
    renameConversation(DEFAULT_CONVERSATION_ID, '   ');
    expect(get(conversationStore).conversations[0].title).toBe(NEW_CHAT_TITLE);
  });

  it('applyAutoTitle replaces the default title with the first prompt (short)', () => {
    applyAutoTitle(DEFAULT_CONVERSATION_ID, 'короткий запрос');
    expect(get(conversationStore).conversations[0].title).toBe('короткий запрос');
  });

  it('applyAutoTitle truncates a long prompt at a word boundary with ellipsis', () => {
    const longPrompt = 'это очень длинный запрос который превышает сорок символов и должен быть обрезан по границе слова';
    applyAutoTitle(DEFAULT_CONVERSATION_ID, longPrompt);
    const title = get(conversationStore).conversations[0].title;
    expect(title.endsWith('…')).toBe(true);
    expect(title.length).toBeLessThanOrEqual(41);
    expect(longPrompt.startsWith(title.slice(0, -1).split('…')[0])).toBe(true);
  });

  it('applyAutoTitle does not overwrite a non-default title', () => {
    renameConversation(DEFAULT_CONVERSATION_ID, 'Закреплённое имя');
    applyAutoTitle(DEFAULT_CONVERSATION_ID, 'новый запрос');
    expect(get(conversationStore).conversations[0].title).toBe('Закреплённое имя');
  });

  it('applyAutoTitle ignores an empty prompt', () => {
    applyAutoTitle(DEFAULT_CONVERSATION_ID, '   ');
    expect(get(conversationStore).conversations[0].title).toBe(NEW_CHAT_TITLE);
  });

  it('getActiveConversationId returns the active id', () => {
    const id = createConversation();
    expect(getActiveConversationId()).toBe(id);
  });

  it('resetConversationStore restores the default state', () => {
    createConversation();
    createConversation();
    resetConversationStore();
    const state = get(conversationStore);
    expect(state.conversations).toHaveLength(1);
    expect(state.activeId).toBe(DEFAULT_CONVERSATION_ID);
  });
});
