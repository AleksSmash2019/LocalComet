/**
 * Checkpoint timeline / compare / restore — thin typed store over the Rust
 * checkpoint authority. No mutation logic lives here: every capability
 * decision is a Tauri command; the store only models truthful UI states.
 */

import { invoke } from '@tauri-apps/api/core';
import { errorDisplayText, normalizeUnknownError } from '$lib/errors/normalizedError';

export interface CheckpointRow {
  readonly checkpoint_id: string;
  readonly parent_checkpoint_id: string | null;
  readonly patch_id: string;
  readonly task_id: string;
  readonly step_id: string;
  readonly status: string;
  readonly trigger: string;
  readonly paths: readonly string[];
  readonly operations: readonly string[];
  readonly before_sha256: Readonly<Record<string, string>>;
  readonly after_sha256: Readonly<Record<string, string>>;
  readonly ownership: string;
}

export type CompareEntry = 'identical' | 'missing' | { modified: true; current_sha256: string };

export type TimelineState =
  | { readonly kind: 'idle' }
  | { readonly kind: 'loading' }
  | { readonly kind: 'ready'; readonly rows: readonly CheckpointRow[] }
  | { readonly kind: 'comparing'; readonly checkpointId: string }
  | {
      readonly kind: 'compared';
      readonly checkpointId: string;
      readonly compare: Readonly<Record<string, CompareEntry>>;
    }
  | { readonly kind: 'restore_approval_required'; readonly checkpointId: string }
  | { readonly kind: 'restoring'; readonly checkpointId: string }
  | {
      readonly kind: 'restored';
      readonly checkpointId: string;
      readonly restored: number;
      /** Backend grant id proving the one-time approval was consumed. */
      readonly grantConsumed: boolean;
    }
  | { readonly kind: 'conflict'; readonly checkpointId: string; readonly message: string }
  | {
      readonly kind: 'restore_task_approval_required';
      readonly taskId: string;
      readonly checkpointIds: readonly string[];
    }
  | { readonly kind: 'restoring_task'; readonly taskId: string }
  | {
      readonly kind: 'restored_task';
      readonly taskId: string;
      readonly restored: number;
      readonly checkpoints: number;
      readonly grantConsumed: boolean;
    }
  | { readonly kind: 'restore_task_conflict'; readonly taskId: string; readonly message: string }
  | { readonly kind: 'failed'; readonly message: string };

/** Wire shape of the Rust ApprovalEnvelope (serde camelCase). */
interface ApprovalEnvelope {
  readonly token: string;
  readonly approvalId: string;
  readonly callId: string;
}

function normalizeError(error: unknown): { code: string; message: string } {
  const normalized = normalizeUnknownError(error);
  // Typed codes surface as-is; unknown shapes keep the human fallback text.
  const code = normalized.code === 'unknown_error' ? 'unknown_error' : normalized.code;
  const message =
    normalized.message === '' || code === 'unknown_error'
      ? errorDisplayText(error)
      : normalized.message;
  return { code, message: message || code };
}

export async function listCheckpoints(): Promise<readonly CheckpointRow[]> {
  const rows = await invoke('checkpoint_list');
  return Array.isArray(rows) ? (rows as CheckpointRow[]) : [];
}

/** Group rows by task, newest-first inside each group (backend order preserved). */
export function groupByTask(
  rows: readonly CheckpointRow[]
): ReadonlyArray<{ readonly taskId: string; readonly items: readonly CheckpointRow[] }> {
  const groups: Array<{ taskId: string; items: CheckpointRow[] }> = [];
  for (const row of rows) {
    let group = groups.find((g) => g.taskId === row.task_id);
    if (!group) {
      group = { taskId: row.task_id, items: [] };
      groups.push(group);
    }
    group.items.push(row);
  }
  return groups;
}

export class CheckpointTimeline {
  private state: TimelineState = { kind: 'idle' };

  snapshot(): TimelineState {
    return this.state;
  }

  async refresh(): Promise<void> {
    this.state = { kind: 'loading' };
    try {
      const rows = await listCheckpoints();
      this.state = { kind: 'ready', rows };
    } catch (error) {
      const { message } = normalizeError(error);
      this.state = { kind: 'failed', message };
    }
  }

  /** `compare_only` — read-only drift report; never mutates anything. */
  async compare(checkpointId: string): Promise<void> {
    if (this.state.kind !== 'ready') return;
    this.state = { kind: 'comparing', checkpointId };
    try {
      const raw = await invoke('checkpoint_compare', { checkpointId });
      const compare =
        raw && typeof raw === 'object'
          ? ((raw as { compare?: Record<string, CompareEntry> }).compare ?? {})
          : {};
      this.state = { kind: 'compared', checkpointId, compare };
    } catch (error) {
      this.state = { kind: 'failed', message: normalizeError(error).message };
    }
  }

  /**
   * Restore flow: the visible confirm gate stays as a user-facing double
   * check, but authorization is backend-owned: `checkpoint_restore_approval`
   * mints a one-time scoped envelope (Rust builds the canonical input from
   * confirmed workspace/session/manifest digests), then
   * `checkpoint_restore_files` consumes it atomically before mutating.
   */
  async requestRestore(checkpointId: string): Promise<void> {
    if (this.state.kind !== 'ready' && this.state.kind !== 'compared') return;
    this.state = { kind: 'restore_approval_required', checkpointId };
  }

  async confirmRestore(checkpointId: string): Promise<void> {
    if (this.state.kind !== 'restore_approval_required') return;
    this.state = { kind: 'restoring', checkpointId };
    try {
      // Step 1 — mint the scoped one-time grant for THIS checkpoint id.
      const envelope = (await invoke('checkpoint_restore_approval', {
        request: { operation: 'restore_files', checkpointIds: [checkpointId] }
      })) as ApprovalEnvelope;
      // Step 2 — backend consumes the grant BEFORE any file changes.
      const raw = await invoke('checkpoint_restore_files', {
        checkpointId,
        token: envelope.token,
        approvalId: envelope.approvalId,
        callId: envelope.callId
      });
      const restored =
        raw && typeof raw === 'object' ? Number((raw as { restored?: number }).restored ?? 0) : 0;
      const grantConsumed =
        raw && typeof raw === 'object'
          ? (raw as { approval_consumed?: boolean }).approval_consumed === true
          : false;
      this.state = { kind: 'restored', checkpointId, restored, grantConsumed };
    } catch (error) {
      const { code, message } = normalizeError(error);
      this.state =
        code === 'restore_conflict'
          ? { kind: 'conflict', checkpointId, message }
          : { kind: 'failed', message };
    }
  }

  /**
   * Task-level restore flow: explicit approval gate first, then the backend
   * unwinds every checkpoint of the task newest-first. Conflict means user
   * edits win and the restore stops at the offending checkpoint.
   */
  async requestRestoreTask(taskId: string, checkpointIds: readonly string[]): Promise<void> {
    if (this.state.kind !== 'ready' && this.state.kind !== 'compared') return;
    if (checkpointIds.length === 0) return;
    this.state = { kind: 'restore_task_approval_required', taskId, checkpointIds };
  }

  async confirmRestoreTask(): Promise<void> {
    if (this.state.kind !== 'restore_task_approval_required') return;
    const { taskId, checkpointIds } = this.state;
    this.state = { kind: 'restoring_task', taskId };
    try {
      // Step 1 — mint the scoped one-time grant for THIS ordered id set.
      const envelope = (await invoke('checkpoint_restore_approval', {
        request: { operation: 'restore_task', checkpointIds: [...checkpointIds] }
      })) as ApprovalEnvelope;
      // Step 2 — backend consumes the grant BEFORE unwinding anything.
      const raw = await invoke('checkpoint_restore_task', {
        checkpointIds: [...checkpointIds],
        token: envelope.token,
        approvalId: envelope.approvalId,
        callId: envelope.callId
      });
      const restored =
        raw && typeof raw === 'object' ? Number((raw as { restored?: number }).restored ?? 0) : 0;
      const checkpoints =
        raw && typeof raw === 'object'
          ? Number((raw as { checkpoints?: number }).checkpoints ?? 0)
          : 0;
      const grantConsumed =
        raw && typeof raw === 'object'
          ? (raw as { approval_consumed?: boolean }).approval_consumed === true
          : false;
      this.state = { kind: 'restored_task', taskId, restored, checkpoints, grantConsumed };
    } catch (error) {
      const { code, message } = normalizeError(error);
      this.state =
        code === 'restore_conflict'
          ? { kind: 'restore_task_conflict', taskId, message }
          : { kind: 'failed', message };
    }
  }

  cancel(): void {
    // Bounded cancellation: only in-flight gates collapse back to idle.
    if (
      this.state.kind === 'comparing' ||
      this.state.kind === 'restore_approval_required' ||
      this.state.kind === 'restoring' ||
      this.state.kind === 'restore_task_approval_required' ||
      this.state.kind === 'restoring_task'
    ) {
      this.state = { kind: 'idle' };
    }
  }
}
