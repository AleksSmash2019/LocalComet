import { derived, get, writable } from 'svelte/store';
import { requestApproval, runToolCall } from '$lib/bridge/approval';

import type { ApprovalEnvelope } from '$lib/bridge/approval';

export interface PendingApproval {
  tool: string;
  input: unknown;
  envelope: ApprovalEnvelope | null;
}

export type ApprovalPhase = 'idle' | 'pending' | 'requesting' | 'executing' | 'error';

export interface ApprovalFlowState {
  pending: PendingApproval | null;
  phase: ApprovalPhase;
  errorCode: string | null;
}

const INITIAL_STATE: ApprovalFlowState = { pending: null, phase: 'idle', errorCode: null };

export const approvalStore = writable<ApprovalFlowState>(INITIAL_STATE);

export const hasPendingApproval = derived(approvalStore, ($state) => $state.pending !== null);

export function resetApprovalStore(): void {
  approvalStore.set(INITIAL_STATE);
}

export function requestApprovalForTool(tool: string, input: unknown): void {
  approvalStore.set({ pending: { tool, input, envelope: null }, phase: 'pending', errorCode: null });
}

export function rejectApproval(): void {
  approvalStore.set(INITIAL_STATE);
}

function errorCodeOf(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof (error as { code: unknown }).code === 'string'
  ) {
    return (error as { code: string }).code;
  }
  return 'internal_error';
}

export async function confirmApproval(): Promise<void> {
  const current = get(approvalStore);
  if (!current.pending) return;
  const { tool, input } = current.pending;
  approvalStore.update((state) => ({ ...state, phase: 'requesting', errorCode: null }));
  try {
    const envelope = await requestApproval(tool, input);
    approvalStore.update((state) => ({
      ...state,
      pending: state.pending ? { ...state.pending, envelope } : state.pending,
      phase: 'executing'
    }));
    await runToolCall(tool, input, envelope);
    approvalStore.set(INITIAL_STATE);
  } catch (error) {
    const code = errorCodeOf(error);
    approvalStore.update((state) => ({ ...state, phase: 'error', errorCode: code }));
  }
}
