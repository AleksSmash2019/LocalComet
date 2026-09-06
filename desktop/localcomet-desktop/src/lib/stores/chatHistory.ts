/**
 * Chat history persistence (localStorage).
 *
 * Scope: the conversation list and finished/visible chat messages survive an
 * app restart. In-flight turns never persist (a mounted frontend is a new UI
 * session per AppShell contract): messages with a non-terminal assistant
 * state are dropped, and `demo` seed messages are never stored.
 *
 * Bounds (INV: no unbounded storage): the serialized record is capped; the
 * oldest messages drop first, then whole conversations. Individual fields are
 * pre-capped so one message can never evict the whole history.
 */
import type { MockMessage } from '$lib/data/mockData';
import { DEFAULT_CONVERSATION_ID, type ConversationMeta } from './conversationStore';

export const CHAT_HISTORY_KEY = 'localcomet.chat.history.v1';

/**
 * Shared coalesced-save entry point. Lives here (not in shellStore) so the
 * conversation store can also trigger saves; chatHistory only imports types
 * from conversationStore, so the module graph stays acyclic.
 */
let saveTimer: ReturnType<typeof setTimeout> | null = null;
let saveRunner: (() => void) | null = null;

export function setChatHistorySaveRunner(runner: () => void): void {
  saveRunner = runner;
}

export function scheduleChatHistorySave(): void {
  if (saveTimer !== null) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveTimer = null;
    saveRunner?.();
  }, 500);
}

const MAX_RECORD_BYTES = 256 * 1024;
const MAX_MESSAGES = 400;
const MAX_CONVERSATIONS = 50;
const MAX_TOOL_RESULT_CHARS = 64 * 1024;
const MAX_STORED_BODY_CHARS = 256 * 1024;
const MAX_STORED_REASONING_CHARS = 32 * 1024;

const TERMINAL_STATES = new Set(['completed', 'cancelled', 'timed_out', 'failed']);
const TOOL_STATUSES = new Set(['PASS', 'WAITING', 'BLOCKED', 'SKIPPED', 'FAIL', 'UNVERIFIED']);

export interface PersistedChatRecord {
  version: 1;
  activeId: string | null;
  conversations: ConversationMeta[];
  messages: MockMessage[];
}

function clampString(value: unknown, max: number): string {
  return typeof value === 'string' ? value.slice(0, max) : '';
}

function sanitizeToolCall(raw: unknown): Record<string, unknown> | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const record = raw as Record<string, unknown>;
  const operation = typeof record.operation === 'string' ? record.operation.slice(0, 64) : '';
  if (!operation) return null;
  const status = typeof record.status === 'string' && TOOL_STATUSES.has(record.status)
    ? record.status
    : 'SKIPPED';
  return {
    operation,
    target: clampString(record.target, 8192),
    status,
    elapsed: clampString(record.elapsed, 32),
    detail: clampString(record.detail, 4096),
    result: clampString(record.result, MAX_TOOL_RESULT_CHARS)
  };
}

function sanitizeMessage(raw: unknown): MockMessage | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const record = raw as Record<string, unknown>;
  const role = record.role === 'user' || record.role === 'assistant' ? record.role : null;
  const id = clampString(record.id, 128);
  const requestId = typeof record.requestId === 'string' && /^[0-9a-f]{24}$/.test(record.requestId)
    ? record.requestId
    : undefined;
  if (!role || !id || !requestId) return null;
  const state = TERMINAL_STATES.has(record.state as string) ? record.state as MockMessage['state'] : undefined;
  // In-flight turns never persist: a restored turn cannot resume its stream.
  if (role === 'assistant' && !state) return null;
  const conversationId = typeof record.conversationId === 'string'
    ? record.conversationId.slice(0, 64)
    : undefined;
  const toolCalls = Array.isArray(record.toolCalls)
    ? record.toolCalls.slice(0, 32)
        .map(sanitizeToolCall)
        .filter((call): call is Record<string, unknown> => call !== null)
        .map((call) => call as unknown as MockMessage['toolCalls'] extends (infer T)[] | undefined ? T : never)
    : undefined;
  const message: MockMessage = {
    id,
    role,
    body: clampString(record.body, MAX_STORED_BODY_CHARS),
    requestId,
    ...(conversationId ? { conversationId } : {}),
    ...(state ? { state } : {}),
    ...(typeof record.error === 'string' ? { error: record.error.slice(0, 240) } : {}),
    ...(record.demo === true ? { demo: true } : {}),
    ...(toolCalls && toolCalls.length > 0 ? { toolCalls } : {}),
    ...(typeof record.reasoning === 'string'
      ? { reasoning: record.reasoning.slice(0, MAX_STORED_REASONING_CHARS) }
      : {}),
    ...(typeof record.effort === 'string' ? { effort: record.effort as MockMessage['effort'] } : {})
  };
  return message;
}

function sanitizeConversation(raw: unknown): ConversationMeta | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const record = raw as Record<string, unknown>;
  const id = clampString(record.id, 64);
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(id)) return null;
  return {
    id,
    title: clampString(record.title, 120) || 'new_chat',
    createdAt: typeof record.createdAt === 'number' && Number.isSafeInteger(record.createdAt) && record.createdAt > 0
      ? record.createdAt
      : 0
  };
}

export function persistChatHistory(
  conversations: ConversationMeta[],
  messages: MockMessage[],
  activeId: string
): void {
  if (typeof localStorage === 'undefined') return;
  try {
    const storableMessages = messages
      .filter((message) => !message.demo && message.requestId)
      .filter((message) => message.role === 'user' || (message.state && TERMINAL_STATES.has(message.state)))
      .map((message) => (message.toolCalls
        ? {
          ...message,
          toolCalls: message.toolCalls.map((call) => ({ ...call, result: clampString(call.result, MAX_TOOL_RESULT_CHARS) }))
        }
        : message));
    const seenConversations = new Set<string>();
    for (const message of storableMessages) {
      if (message.conversationId) seenConversations.add(message.conversationId);
    }
    const storableConversations = conversations
      .slice(0, MAX_CONVERSATIONS)
      .filter((conversation) =>
        // The default conversation is always kept so a fresh "new chat" is
        // available right after restore, even with no stored messages yet.
        conversation.id === DEFAULT_CONVERSATION_ID ||
        seenConversations.has(conversation.id) ||
        conversation.id === activeId);
    const record: PersistedChatRecord = {
      version: 1,
      activeId,
      conversations: storableConversations,
      messages: storableMessages.slice(-MAX_MESSAGES)
    };
    let serialized = JSON.stringify(record);
    // Hard envelope: shed the oldest data until the record fits.
    while (serialized.length > MAX_RECORD_BYTES && record.messages.length > 2) {
      record.messages = record.messages.slice(1);
      serialized = JSON.stringify(record);
    }
    if (serialized.length <= MAX_RECORD_BYTES) {
      localStorage.setItem(CHAT_HISTORY_KEY, serialized);
    }
  } catch {
    // Storage unavailable or full: chat still works in memory.
  }
}

export function loadChatHistory(): PersistedChatRecord {
  const empty: PersistedChatRecord = { version: 1, activeId: null, conversations: [], messages: [] };
  if (typeof localStorage === 'undefined') return empty;
  try {
    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    if (!raw) return empty;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return empty;
    const record = parsed as Record<string, unknown>;
    if (record.version !== 1) return empty;
    const conversations = Array.isArray(record.conversations)
      ? record.conversations.slice(0, MAX_CONVERSATIONS)
          .map(sanitizeConversation)
          .filter((conversation): conversation is ConversationMeta => conversation !== null)
      : [];
    const messages = Array.isArray(record.messages)
      ? record.messages.slice(-MAX_MESSAGES)
          .map(sanitizeMessage)
          .filter((message): message is MockMessage => message !== null)
      : [];
    const known = new Set(conversations.map((conversation) => conversation.id));
    const filteredMessages = messages.filter((message) => !message.conversationId || known.has(message.conversationId));
    const activeId = typeof record.activeId === 'string' && known.has(record.activeId)
      ? record.activeId
      : null;
    return { version: 1, activeId, conversations, messages: filteredMessages };
  } catch {
    return empty;
  }
}

export function clearChatHistory(): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.removeItem(CHAT_HISTORY_KEY);
  } catch {
    // ignore
  }
}
