/**
 * Single tool-call result classifier shared by the gateway store and the tool
 * card renderer (previously two divergent ad-hoc parsers, with zero Rust-side
 * agreement on what counts as success).
 *
 * Semantics (master prompt, Этап 2 unified result contract):
 * - pending (e.g. launch_pending) is never a success;
 * - success requires the full verified contract for computer_use.result.v1
 *   (status completed AND terminal AND succeeded AND verification verified);
 * - legacy shapes without schema_version may only be "unverified" successes,
 *   never verified;
 * - blocked, failed and malformed never become PASS.
 */
export const COMPUTER_USE_RESULT_SCHEMA = 'computer_use.result.v1';

export type ToolCallOutcomeKind =
  | 'pending'
  | 'verified_success'
  | 'unverified_success'
  | 'blocked'
  | 'failed'
  | 'malformed';

export interface ToolCallOutcome {
  readonly kind: ToolCallOutcomeKind;
  readonly record: Record<string, unknown> | null;
  readonly reason: string;
}

const PENDING_STATUSES: ReadonlySet<string> = new Set(['launch_pending', 'awaiting_observation']);

function reasonOf(record: Record<string, unknown>, fallback: string): string {
  if (typeof record.reason === 'string' && record.reason) return record.reason;
  if (typeof record.error === 'string' && record.error) return record.error;
  return fallback;
}

function isBlockedRecord(record: Record<string, unknown>, status: string): boolean {
  return record.blocked === true || status === 'blocked' || status === 'requires_confirmation';
}

export function parseToolCallResult(tool: string, raw: unknown): ToolCallOutcome {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    return { kind: 'malformed', record: null, reason: 'tool returned no confirmed success' };
  }
  const record = raw as Record<string, unknown>;
  const status = String(record.status ?? '').toLowerCase();
  const verification = String(record.verification ?? '').toLowerCase();
  const pending =
    record.terminal === false ||
    PENDING_STATUSES.has(status) ||
    verification === 'pending';

  if (tool === 'computer_use') {
    if (pending) {
      return { kind: 'pending', record, reason: reasonOf(record, 'action is pending verification') };
    }
    if (record.schema_version === COMPUTER_USE_RESULT_SCHEMA) {
      if (
        status === 'completed' &&
        record.terminal === true &&
        record.succeeded === true &&
        (verification === 'verified' || verification === 'not_applicable')
      ) {
        // 'verified' = explicit backend postcondition (e.g. window readiness);
        // 'not_applicable' = the action's own execution report is the result
        // (wait/screenshot/paste primitives). A bare missing or unknown
        // verification value is never a success here.
        return { kind: 'verified_success', record, reason: '' };
      }
      if (isBlockedRecord(record, status)) {
        return { kind: 'blocked', record, reason: reasonOf(record, 'action was blocked by policy') };
      }
      return { kind: 'failed', record, reason: reasonOf(record, 'tool execution failed') };
    }
    // Legacy compatibility adapter: ok=true without the envelope is at most
    // an unverified success and is never displayed as verified.
    if (isBlockedRecord(record, status)) {
      return { kind: 'blocked', record, reason: reasonOf(record, 'action was blocked by policy') };
    }
    if (record.ok === true) {
      return { kind: 'unverified_success', record, reason: '' };
    }
    return { kind: 'failed', record, reason: reasonOf(record, 'tool returned no confirmed success') };
  }

  // Non-computer_use tools (files.*, web.*): the sidecar returns the payload
  // for a successful read/guarded operation without an ok flag, and failures
  // arrive as rejected invokes; only explicit blocked/failed markers count.
  if (isBlockedRecord(record, status)) {
    return { kind: 'blocked', record, reason: reasonOf(record, 'action was blocked by policy') };
  }
  if (record.ok === false || (typeof record.error === 'string' && record.error)) {
    return { kind: 'failed', record, reason: reasonOf(record, 'tool execution failed') };
  }
  return { kind: 'unverified_success', record, reason: '' };
}
