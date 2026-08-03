import { derived, get, writable } from 'svelte/store';

export interface ConversationMeta {
  id: string;
  title: string;
  createdAt: number;
}

export interface ConversationState {
  conversations: ConversationMeta[];
  activeId: string;
}

export const DEFAULT_CONVERSATION_ID = 'local-chat';
export const NEW_CHAT_TITLE = 'new_chat';
const AUTO_TITLE_MAX_CHARS = 40;
const CHAT_SESSION_ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;

function createDefaultConversation(): ConversationMeta {
  return { id: DEFAULT_CONVERSATION_ID, title: NEW_CHAT_TITLE, createdAt: Date.now() };
}

function initialState(): ConversationState {
  const conversation = createDefaultConversation();
  return { conversations: [conversation], activeId: conversation.id };
}

export const conversationStore = writable<ConversationState>(initialState());

export const activeConversation = derived(conversationStore, ($state) => {
  return $state.conversations.find((c) => c.id === $state.activeId) ?? $state.conversations[0] ?? null;
});

let conversationCounter = 0;

function generateConversationId(): string {
  conversationCounter += 1;
  const id = `chat-${Date.now().toString(36)}-${conversationCounter}`;
  if (!CHAT_SESSION_ID_RE.test(id)) {
    throw new Error('generated conversation id failed chatSessionId validation');
  }
  return id;
}

export function createConversation(): string {
  const id = generateConversationId();
  conversationStore.update((state) => ({
    conversations: [{ id, title: NEW_CHAT_TITLE, createdAt: Date.now() }, ...state.conversations],
    activeId: id
  }));
  return id;
}

export function selectConversation(id: string): void {
  conversationStore.update((state) =>
    state.conversations.some((c) => c.id === id) ? { ...state, activeId: id } : state
  );
}

export function renameConversation(id: string, title: string): void {
  const trimmed = title.trim();
  if (!trimmed) return;
  conversationStore.update((state) => ({
    ...state,
    conversations: state.conversations.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
  }));
}

function autoTitleFromPrompt(prompt: string): string {
  if (prompt.length <= AUTO_TITLE_MAX_CHARS) return prompt;
  const sliced = prompt.slice(0, AUTO_TITLE_MAX_CHARS);
  const lastSpace = sliced.lastIndexOf(' ');
  const trimmed = lastSpace > 0 ? sliced.slice(0, lastSpace) : sliced;
  return `${trimmed}…`;
}

export function applyAutoTitle(id: string, prompt: string): void {
  const cleaned = prompt.trim();
  if (!cleaned) return;
  conversationStore.update((state) => ({
    ...state,
    conversations: state.conversations.map((c) =>
      c.id === id && c.title === NEW_CHAT_TITLE ? { ...c, title: autoTitleFromPrompt(cleaned) } : c
    )
  }));
}

export function getActiveConversationId(): string {
  return get(conversationStore).activeId;
}

export function resetConversationStore(): void {
  conversationCounter = 0;
  conversationStore.set(initialState());
}
