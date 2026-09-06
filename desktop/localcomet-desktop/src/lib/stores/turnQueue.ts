/**
 * Single-slot send queue for the chat composer.
 *
 * When a model turn is already running, a new submit no longer dies on the
 * busy guard: the draft is queued (visible, replaceable, cancelable) and
 * auto-submits as soon as the current turn reaches a terminal state.
 *
 * One slot only — a queue of turns behind a single sidecar turn pipeline
 * would hide real latency; a visible "next message" slot is honest. The slot
 * is per conversation: switching conversations swaps the visible queued
 * draft out of the slot (it is NOT preserved for the old conversation).
 */
import { writable, get } from 'svelte/store';

export interface QueuedTurn {
  conversationId: string;
  draft: string;
  fileIds: readonly string[];
}

export const queuedTurnStore = writable<QueuedTurn | null>(null);

export function queueTurn(conversationId: string, draft: string, fileIds: readonly string[] = []): boolean {
  const clean = draft.trim();
  if (!clean) return false;
  queuedTurnStore.set({ conversationId, draft: clean, fileIds });
  return true;
}

export function dequeueTurn(): QueuedTurn | null {
  const queued = get(queuedTurnStore);
  queuedTurnStore.set(null);
  return queued;
}

export function clearQueuedTurn(): void {
  queuedTurnStore.set(null);
}
