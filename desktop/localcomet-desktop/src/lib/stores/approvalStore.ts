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
  /** Server-issued approval request identity when a compatibility card is used. */
  requestId?: string;
  /** Canonical digest of the exact input approved by Rust. */
  inputDigest?: string;
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
  /** Canonical SHA-256 digest of the exact input bound by Rust. */
  input_digest: string;
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

const APPROVAL_ID_PATTERN = /^appr_[0-9a-f]{32}$/;
const MODEL_REQUEST_ID_PATTERN = /^[0-9a-f]{24}$/;
const INPUT_DIGEST_PATTERN = /^[0-9a-f]{64}$/;
const MAX_TOOL_NAME_LENGTH = 128;
const MAX_TARGET_SUMMARY_LENGTH = 16_384;
const MAX_SIDE_EFFECT_CATEGORY_LENGTH = 128;
const MAX_MODEL_ACTION_ID_LENGTH = 256;

function boundedString(value: unknown, maxLength: number, allowEmpty = false): value is string {
  return typeof value === 'string' &&
    value.length <= maxLength &&
    (allowEmpty || value.length > 0) &&
    ![...value].some((character) => character.charCodeAt(0) < 0x20 || character.charCodeAt(0) === 0x7f);
}

/**
 * Normalize the Rust event before it reaches any approval DOM or resolver.
 * Tauri event typing is compile-time only; runtime payloads still fail closed.
 */
export function normalizeApprovalPrompt(value: unknown): ActiveApprovalPrompt | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null;
  const candidate = value as Record<string, unknown>;
  const requestId = candidate.request_id;
  const modelRequestId = candidate.model_request_id;
  const modelActionId = candidate.model_action_id;
  const tool = candidate.tool;
  const riskLevel = candidate.risk_level;
  const targetSummary = candidate.target_summary;
  const sideEffectCategory = candidate.side_effect_category;
  const destructive = candidate.destructive;
  const inputDigest = candidate.input_digest;
  const expiresAt = candidate.expires_at_unix_ms;

  if (typeof requestId !== 'string' || !APPROVAL_ID_PATTERN.test(requestId)) return null;
  const hasModelRequestId = modelRequestId !== undefined;
  const hasModelActionId = modelActionId !== undefined;
  if (hasModelRequestId !== hasModelActionId) return null;
  if (modelRequestId !== undefined && (typeof modelRequestId !== 'string' || !MODEL_REQUEST_ID_PATTERN.test(modelRequestId))) return null;
  if (modelActionId !== undefined && !boundedString(modelActionId, MAX_MODEL_ACTION_ID_LENGTH)) return null;
  if (!boundedString(tool, MAX_TOOL_NAME_LENGTH)) return null;
  if (riskLevel !== 'read_only' && riskLevel !== 'guarded' && riskLevel !== 'dangerous') return null;
  if (!boundedString(targetSummary, MAX_TARGET_SUMMARY_LENGTH, true)) return null;
  if (!boundedString(sideEffectCategory, MAX_SIDE_EFFECT_CATEGORY_LENGTH)) return null;
  if (typeof destructive !== 'boolean') return null;
  if (typeof inputDigest !== 'string' || !INPUT_DIGEST_PATTERN.test(inputDigest)) return null;
  if (expiresAt !== undefined && (typeof expiresAt !== 'number' || !Number.isSafeInteger(expiresAt) || expiresAt <= 0)) return null;

  return {
    request_id: requestId,
    ...(modelRequestId === undefined ? {} : { model_request_id: modelRequestId }),
    ...(modelActionId === undefined ? {} : { model_action_id: modelActionId }),
    tool,
    risk_level: riskLevel,
    target_summary: targetSummary,
    side_effect_category: sideEffectCategory,
    destructive,
    input_digest: inputDigest,
    ...(expiresAt === undefined ? {} : { expires_at_unix_ms: expiresAt })
  };
}

export function setApprovalCorrelation(correlation: ApprovalCorrelation): void {
  pendingApprovalCorrelation = { ...correlation };
}

export function getApprovalCorrelation(): ApprovalCorrelation | null {
  return pendingApprovalCorrelation ? { ...pendingApprovalCorrelation } : null;
}

export function clearApprovalCorrelation(): void {
  pendingApprovalCorrelation = null;
}

export function setApprovalPrompt(value: unknown): boolean {
  const prompt = normalizeApprovalPrompt(value);
  if (!prompt) {
    const previous = get(approvalPrompt);
    if (previous) {
      void resolveToolApproval(previous.request_id, 'reject').catch(() => undefined);
    }
    clearApprovalPrompt();
    console.warn('Rejected malformed request_tool_approval payload');
    return false;
  }
  const previous = get(approvalPrompt);
  if (previous && previous.request_id !== prompt.request_id) {
    void resolveToolApproval(previous.request_id, 'reject').catch(() => undefined);
  }
  const serverCorrelation = prompt.model_request_id && prompt.model_action_id
    ? { modelRequestId: prompt.model_request_id, modelActionId: prompt.model_action_id }
    : null;
  const pendingCorrelation = pendingApprovalCorrelation;
  if (
    serverCorrelation &&
    pendingCorrelation &&
    (serverCorrelation.modelRequestId !== pendingCorrelation.modelRequestId ||
      serverCorrelation.modelActionId !== pendingCorrelation.modelActionId)
  ) {
    // The Rust event is authoritative. A mismatch is diagnostic evidence, not
    // a reason to silently overwrite the server identity with mutable UI state.
    console.warn('Approval correlation mismatch; using server-authenticated identity');
  }
  // A server event without correlation is intentionally uncorrelated. Do not
  // attach a stale mutable UI pair to it: that would make the DOM claim a
  // model-turn identity which Rust never authenticated for this prompt.
  approvalPrompt.set(serverCorrelation ? {
    ...prompt,
    model_request_id: serverCorrelation.modelRequestId,
    model_action_id: serverCorrelation.modelActionId
  } : prompt);
  clearApprovalCorrelation();
  approvalPromptActive.set(true);
  return true;
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
    const envelope = await requestApproval(tool, input, {
      requestId: callbacks?.requestId,
      actionId: callbacks?.actionId
    });
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
