import { derived, get, writable } from 'svelte/store';
import { requestApproval, runToolCall } from '$lib/bridge/approval';

import type { ApprovalEnvelope } from '$lib/bridge/approval';

export interface ApprovalExecutionCallbacks {
  onResult?: (result: unknown) => void;
  onError?: (error: unknown) => void;
}

export interface PendingApproval {
  tool: string;
  input: unknown;
  envelope: ApprovalEnvelope | null;
  callbacks?: ApprovalExecutionCallbacks;
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

async function executeApprovalInBackground(
  tool: string,
  input: unknown,
  callbacks?: ApprovalExecutionCallbacks
): Promise<void> {
  approvalStore.set({ pending: null, phase: 'requesting', errorCode: null });
  try {
    const envelope = await requestApproval(tool, input);
    approvalStore.set({ pending: null, phase: 'executing', errorCode: null });
    const result = await runToolCall(tool, input, envelope);
    callbacks?.onResult?.(result);
    approvalStore.set(INITIAL_STATE);
  } catch (error) {
    callbacks?.onError?.(error);
    approvalStore.set({ pending: null, phase: 'error', errorCode: errorCodeOf(error) });
  }
}

/**
 * Guarded and dangerous tool calls use the Rust approval boundary in the
 * background. Rust still mints and atomically consumes the scoped one-time
 * token; this function deliberately does not create a user-facing card.
 */
export function requestApprovalForTool(
  tool: string,
  input: unknown,
  callbacks?: ApprovalExecutionCallbacks
): void {
  void executeApprovalInBackground(tool, input, callbacks);
}

/**
 * Kept as a compatibility entry point for existing UI/tests. Production tool
 * requests no longer create a pending card, so this is normally a no-op.
 */
export function rejectApproval(): void {
  const current = get(approvalStore);
  current.pending?.callbacks?.onError?.({
    code: 'approval_rejected',
    message: 'User rejected the requested tool action'
  });
  approvalStore.set(INITIAL_STATE);
}

export async function confirmApproval(): Promise<void> {
  const current = get(approvalStore);
  if (!current.pending) return;
  const { tool, input, callbacks } = current.pending;
  await executeApprovalInBackground(tool, input, callbacks);
}
