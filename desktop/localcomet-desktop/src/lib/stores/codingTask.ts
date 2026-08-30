/**
 * Coding task UI store — thin typed transport over the Rust orchestrator.
 * Backend truth outranks optimistic assumptions: COMPLETED appears only
 * after coding_start returns a backend-verified result.
 *
 * Authorization (P0): every start first mints a one-time scoped approval
 * (`coding_start_approval`) bound server-side to files.write × patch digest ×
 * confirmed workspace × session; `coding_start` consumes it atomically
 * BEFORE any filesystem mutation. No token → typed rejection, no write.
 */

import { invoke } from '@tauri-apps/api/core';
import {
  errorDisplayText,
  normalizeUnknownError,
  type NormalizedError
} from '$lib/errors/normalizedError';

export type CodingStatus =
  | 'idle'
  | 'starting'
  | 'running'
  /** Strong truthful success: compile + executed focused test, exit 0. */
  | 'completed'
  /** Honest weaker outcome: clean compile only; behavior NOT verified. */
  | 'compile_verified_only'
  | 'failed'
  | 'blocked'
  | 'cancelled'
  | 'paused_for_review'
  | { readonly error: string };

export interface CodingEvent {
  readonly seq: number;
  readonly event_type: string;
  readonly state_before: string;
  readonly state_after: string;
  readonly payload: Record<string, unknown>;
  readonly event_hash: string;
}

export type PersistedCodingStatus =
  | 'completed'
  | 'compile_verified_only'
  | 'failed'
  | 'blocked'
  | 'cancelled'
  | 'paused_for_review'
  | 'corrupt';

export interface PersistedCodingTask {
  readonly task_id: string;
  readonly status: PersistedCodingStatus;
  readonly verification_level?: 'behavior_verified' | 'compile_verified_only' | 'none';
  readonly state?: string;
  readonly last_seq?: number;
  readonly terminal?: boolean;
  readonly requires_review?: boolean;
  readonly reason?: string;
}

export interface CodingRecoveryResponse {
  readonly task_id: string;
  readonly status: Exclude<PersistedCodingStatus, 'corrupt'>;
  readonly verification_level: 'behavior_verified' | 'compile_verified_only' | 'none';
  readonly state: string;
  readonly terminal: boolean;
  readonly requires_review: boolean;
  readonly reason: string;
  readonly events: readonly CodingEvent[];
}

export interface CodingStartResponse {
  readonly task_id: string;
  /** Truthful backend outcome vocabulary (P1). */
  readonly status:
    | 'behavior_verified'
    | 'compile_verified_only'
    | 'failed'
    | 'blocked'
    | 'cancelled'
    | 'paused_for_review';
  /** How strongly the change was verified for THIS run. */
  readonly verification_level: 'behavior_verified' | 'compile_verified_only' | 'none';
  readonly applied_paths: readonly string[];
  readonly error_diagnostics: number;
  readonly generation_hash: string;
  readonly test_exit_code: number | null;
  readonly reason: string;
  readonly grant_id?: string;
  readonly approval_consumed?: boolean;
}

interface ApprovalEnvelope {
  readonly token: string;
  /** Wire shape follows the Rust ApprovalEnvelope serde camelCase rename. */
  readonly approvalId: string;
  readonly callId: string;
}

function normalizeError(error: unknown): string {
  return errorDisplayText(error);
}

function statusFromRecovery(response: CodingRecoveryResponse): CodingStatus {
  switch (response.status) {
    case 'completed':
      return 'completed';
    case 'compile_verified_only':
      return 'compile_verified_only';
    case 'blocked':
      return 'blocked';
    case 'cancelled':
      return 'cancelled';
    case 'failed':
      return 'failed';
    case 'paused_for_review':
      return 'paused_for_review';
    default:
      return { error: 'task_recovery_invalid_status' };
  }
}

async function sha256Hex(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export interface LspDiagnosticsResponse {
  readonly schema_version: string;
  readonly available: boolean;
  /** Present only when available=false — the exact honest reason. */
  readonly reason?: string;
  readonly server?: string;
  readonly generation_hash?: string;
  readonly diagnostics?: readonly {
    readonly file: string;
    readonly line: number;
    readonly column: number;
    readonly code: string;
    readonly severity: string;
    readonly source: string;
    readonly message: string;
    readonly stale: boolean;
  }[];
}

/** Bounded LSP diagnostics probe over the real Tauri seam. */
export async function fetchLspDiagnostics(
  workspacePath: string,
  relPath: string
): Promise<LspDiagnosticsResponse> {
  const raw = await invoke('lsp_diagnostics', { workspacePath, relPath });
  return raw as LspDiagnosticsResponse;
}

export class CodingTaskStore {
  status: CodingStatus = 'idle';
  taskId = '';
  events: readonly CodingEvent[] = [];
  lastResult: CodingStartResponse | null = null;
  /** Read-only inventory recovered from the confirmed workspace ledger. */
  persistedTasks: readonly PersistedCodingTask[] = [];
  recovery: CodingRecoveryResponse | null = null;
  recoveryReason = '';
  /** Versioned envelope of the last rejection — powers diagnostic UI line. */
  lastError: NormalizedError | null = null;

  private cancelFlagId = '';

  async start(workspacePath: string, relPath: string, newContent: string): Promise<void> {
    if (this.status === 'starting' || this.status === 'running') return;
    this.taskId = `task_${Date.now().toString(36)}`;
    this.status = 'starting';
    this.events = [];
    this.recovery = null;
    this.recoveryReason = '';
    this.lastError = null;
    try {
      // Step 1 — mint the one-time scoped grant for THIS exact patch.
      const envelope = (await invoke('coding_start_approval', {
        descriptor: {
          relPath,
          contentSha256: await sha256Hex(newContent),
          taskId: this.taskId,
          patchId: `patch_${this.taskId}`,
          stepId: 'step_1'
        }
      })) as ApprovalEnvelope;

      // Step 2 — backend consumes the grant before touching the workspace.
      const raw = await invoke('coding_start', {
        request: {
          sessionId: '',
          workspacePath,
          relPath,
          newContent,
          taskId: this.taskId,
          patchId: `patch_${this.taskId}`,
          stepId: 'step_1',
          token: envelope.token,
          approvalId: envelope.approvalId,
          callId: envelope.callId
        }
      });
      const res = raw as CodingStartResponse;
      this.lastResult = res;
      // Cancel raced the run: backend already reported a cancelled terminal.
      if (this.cancelFlagId === this.taskId) {
        this.status = 'cancelled';
        return;
      }
      this.cancelFlagId = '';
      // P1 truthfulness: only behavior_verified counts as full success;
      // compile-only is a visibly distinct, weaker outcome.
      this.status =
        res.status === 'behavior_verified'
          ? 'completed'
          : res.status === 'compile_verified_only'
            ? 'compile_verified_only'
            : res.status === 'blocked'
              ? 'blocked'
              : res.status === 'cancelled'
                ? 'cancelled'
                : res.status === 'paused_for_review'
                  ? 'paused_for_review'
                  : 'failed';
    } catch (error) {
      const normalized = normalizeUnknownError(error);
      this.lastError = normalized;
      this.status = { error: normalizeError(error) };
    }
  }

  async refreshPersistedTasks(): Promise<void> {
    try {
      const raw = (await invoke('coding_list_tasks')) as { tasks?: unknown };
      const tasks = Array.isArray(raw?.tasks)
        ? raw.tasks.filter(
            (task): task is PersistedCodingTask =>
              Boolean(task) &&
              typeof task === 'object' &&
              typeof (task as Record<string, unknown>).task_id === 'string' &&
              typeof (task as Record<string, unknown>).status === 'string'
          )
        : [];
      this.persistedTasks = tasks;
    } catch {
      // A missing/unconfirmed workspace remains an honest empty inventory.
    }
  }

  async recover(taskId: string): Promise<void> {
    if (!taskId) return;
    this.lastError = null;
    this.recoveryReason = '';
    try {
      const raw = (await invoke('coding_recover_task', { taskId })) as CodingRecoveryResponse;
      if (
        !raw ||
        raw.task_id !== taskId ||
        !Array.isArray(raw.events) ||
        typeof raw.reason !== 'string' ||
        typeof raw.status !== 'string'
      ) {
        throw new Error('invalid_task_recovery_response');
      }
      this.taskId = taskId;
      this.events = raw.events;
      this.recovery = raw;
      this.recoveryReason = raw.reason;
      this.lastResult = null;
      this.status = statusFromRecovery(raw);
    } catch (error) {
      const normalized = normalizeUnknownError(error);
      this.lastError = normalized;
      this.status = { error: normalizeError(error) };
    }
  }

  async refreshEvents(): Promise<void> {
    if (!this.taskId) return;
    try {
      const raw = await invoke('coding_events', { taskId: this.taskId });
      const parsed = raw as { events?: CodingEvent[] };
      this.events = Array.isArray(parsed?.events) ? parsed.events : [];
    } catch {
      // Bounded poll miss keeps previous events; never fabricates.
    }
  }

  async cancel(): Promise<void> {
    if (this.status !== 'starting' && this.status !== 'running') return;
    this.cancelFlagId = this.taskId;
    try {
      await invoke('coding_cancel', { taskId: this.taskId });
    } catch {
      // Typed no-op when the runner already finished; status stays truthful.
    }
  }

  reset(): void {
    this.status = 'idle';
    this.taskId = '';
    this.events = [];
    this.lastResult = null;
    this.recovery = null;
    this.recoveryReason = '';
    this.lastError = null;
    this.cancelFlagId = '';
  }
}
