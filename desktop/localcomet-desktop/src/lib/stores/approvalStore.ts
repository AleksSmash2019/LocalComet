import { derived, get, writable } from 'svelte/store';
import { requestApproval, resolveToolApproval, runToolCall } from '$lib/bridge/approval';

import type { ApprovalEnvelope } from '$lib/bridge/approval';

export interface ApprovalExecutionCallbacks {
  onResult?: (result: unknown) => void;
  onError?: (error: unknown) => void;
  /** Model-turn correlation; never merged into the tool input object. */
  requestId?: string;
  /** Model tool-call identity; distinct from the one-time approval callId. */
  actionId?: string;
}

export interface PendingApproval {
  tool: string;
  input: unknown;
  envelope: ApprovalEnvelope | null;
  callbacks?: ApprovalExecutionCallbacks;
}

export interface ActiveApprovalPrompt {
  request_id: string;
  /** Model-turn correlation captured before the Rust approval event arrives. */
  model_request_id?: string;
  /** Model provider tool-call ID; distinct from approval call_id. */
  model_action_id?: string;
  tool: string;
  risk_level: string;
  target_summary: string;
  side_effect_category: string;
  destructive: boolean;
  expires_at_unix_ms?: number;
}

export type ApprovalPhase = 'idle' | 'pending' | 'requesting' | 'executing' | 'error';

export interface ApprovalFlowState {
  pending: PendingApproval | null;
  phase: ApprovalPhase;
  errorCode: string | null;
}

const INITIAL_STATE: ApprovalFlowState = { pending: null, phase: 'idle', errorCode: null };

export const approvalStore = writable<ApprovalFlowState>(INITIAL_STATE);

/** True while the Rust frontend approval modal is waiting for a user decision. */
export const approvalPromptActive = writable(false);
export const approvalPrompt = writable<ActiveApprovalPrompt | null>(null);

export interface ApprovalCorrelation {
  modelRequestId: string;
  modelActionId: string;
}

let pendingApprovalCorrelation: ApprovalCorrelation | null = null;

export function setApprovalCorrelation(correlation: ApprovalCorrelation): void {
  pendingApprovalCorrelation = { ...correlation };
}

export function getApprovalCorrelation(): ApprovalCorrelation | null {
  return pendingApprovalCorrelation ? { ...pendingApprovalCorrelation } : null;
}

export function clearApprovalCorrelation(): void {
  pendingApprovalCorrelation = null;
}

export function setApprovalPrompt(prompt: ActiveApprovalPrompt): void {
  const previous = get(approvalPrompt);
  if (previous && previous.request_id !== prompt.request_id) {
    void resolveToolApproval(previous.request_id, 'reject').catch(() => undefined);
  }
  const correlation = pendingApprovalCorrelation;
  approvalPrompt.set(correlation ? {
    ...prompt,
    model_request_id: correlation.modelRequestId,
    model_action_id: correlation.modelActionId
  } : prompt);
  approvalPromptActive.set(true);
}

export function clearApprovalPrompt(): void {
  approvalPrompt.set(null);
  approvalPromptActive.set(false);
  clearApprovalCorrelation();
}

export function setApprovalPromptActive(active: boolean): void {
  approvalPromptActive.set(active);
}

export async function rejectActiveApproval(): Promise<void> {
  const prompt = get(approvalPrompt);
  if (!prompt) return;
  try {
    await resolveToolApproval(prompt.request_id, 'reject');
  } catch {
    // The backend may have already timed out or cancelled the prompt.
  } finally {
    clearApprovalPrompt();
  }
}

export const hasPendingApproval = derived(approvalStore, ($state) => $state.pending !== null);

export function resetApprovalStore(): void {
  approvalStore.set(INITIAL_STATE);
  clearApprovalPrompt();
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
    const result = await runToolCall(
      tool,
      input,
      envelope,
      undefined,
      callbacks?.requestId,
      callbacks?.actionId
    );
    callbacks?.onResult?.(result);
    approvalStore.set(INITIAL_STATE);
  } catch (error) {
    callbacks?.onError?.(error);
    approvalStore.set({ pending: null, phase: 'error', errorCode: errorCodeOf(error) });
  }
}

/**
 * Guarded and dangerous tool calls use the Rust approval boundary. Rust mints
 * and atomically consumes the scoped one-time token; dangerous tools
 * additionally open the user-facing decision card (the `request_tool_approval`
 * event rendered by ApprovalModal) and only issue the token after an explicit
 * Approve decision, so execution below cannot start before user consent.
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
