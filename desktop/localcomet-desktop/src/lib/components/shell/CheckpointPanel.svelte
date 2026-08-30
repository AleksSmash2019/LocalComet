<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n';
  import {
    CheckpointTimeline,
    groupByTask,
    type CompareEntry,
    type CheckpointRow
  } from '$lib/stores/checkpointTimeline';

  const timeline = new CheckpointTimeline();
  // Local render copy: the store is class-based; $-reactivity comes from this.
  let stateKind = 'idle' as string;
  let rows: readonly CheckpointRow[] = [];
  let compareEntries: Readonly<Record<string, CompareEntry>> = {};
  let activeCheckpointId = '';
  let message = '';

  function syncFromStore(): void {
    const snap = timeline.snapshot();
    stateKind = snap.kind;
    if (snap.kind === 'ready') rows = snap.rows;
    if (snap.kind === 'compared') {
      compareEntries = snap.compare;
      activeCheckpointId = snap.checkpointId;
    }
    if (snap.kind === 'conflict' || snap.kind === 'failed') message = snap.message;
  }

  onMount(() => {
    void timeline.refresh().then(syncFromStore);
  });

  async function onCompare(checkpointId: string): Promise<void> {
    await timeline.compare(checkpointId);
    syncFromStore();
  }

  async function onRequestRestore(checkpointId: string): Promise<void> {
    await timeline.requestRestore(checkpointId);
    syncFromStore();
  }

  async function onConfirmRestore(): Promise<void> {
    await timeline.confirmRestore(activeCheckpointId);
    syncFromStore();
    if (timeline.snapshot().kind === 'restored') {
      await timeline.refresh();
      syncFromStore();
    }
  }

  async function onRequestRestoreTask(taskId: string, checkpointIds: readonly string[]): Promise<void> {
    await timeline.requestRestoreTask(taskId, checkpointIds);
    syncFromStore();
  }

  async function onConfirmRestoreTask(): Promise<void> {
    await timeline.confirmRestoreTask();
    syncFromStore();
    const kind = timeline.snapshot().kind;
    if (kind === 'restored_task' || kind === 'restore_task_conflict') {
      await timeline.refresh();
      syncFromStore();
    }
  }

  function onCancel(): void {
    timeline.cancel();
    syncFromStore();
  }

  function describeEntry(entry: CompareEntry): string {
    if (entry === 'identical') return $t('checkpoints.compare_identical');
    if (entry === 'missing') return $t('checkpoints.compare_missing');
    return $t('checkpoints.compare_modified');
  }
</script>

<section aria-labelledby="checkpoints-title" class="checkpoint-panel">
  <h3 id="checkpoints-title">{$t('checkpoints.title')}</h3>

  {#if stateKind === 'loading'}
    <p role="status">{$t('checkpoints.loading')}</p>
  {:else if stateKind === 'failed'}
    <p role="alert">{$t('checkpoints.error_prefix')} {message}</p>
  {:else if stateKind === 'ready' && rows.length === 0}
    <p>{$t('checkpoints.empty')}</p>
  {:else if stateKind === 'ready'}
        {#each groupByTask(rows) as group (group.taskId)}
          <div class="checkpoint-task-group">
            <h4>
              {group.taskId}
              <button
                type="button"
                class="cp-task-restore"
                onclick={() => onRequestRestoreTask(group.taskId, group.items.map((r) => r.checkpoint_id))}
              >
                {$t('checkpoints.restore_task')}
              </button>
            </h4>
        {#each group.items as row (row.checkpoint_id)}
          <article class="checkpoint-row" data-checkpoint-id={row.checkpoint_id}>
            <header>
              <span class="cp-id">{row.checkpoint_id}</span>
              <span class="cp-status">{row.status}</span>
            </header>
            <dl>
              <dt>{$t('checkpoints.patch_id')}</dt><dd>{row.patch_id}</dd>
              <dt>{$t('checkpoints.step_id')}</dt><dd>{row.step_id}</dd>
              <dt>{$t('checkpoints.files')}</dt>
              <dd>{row.paths.join(', ')}</dd>
            </dl>
            <div class="cp-actions">
              <button type="button" onclick={() => onCompare(row.checkpoint_id)}>
                {$t('checkpoints.compare')}
              </button>
              <button type="button" onclick={() => onRequestRestore(row.checkpoint_id)}>
                {$t('checkpoints.restore_files')}
              </button>
            </div>
          </article>
        {/each}
      </div>
    {/each}
  {:else if stateKind === 'comparing'}
    <p role="status">{$t('checkpoints.comparing')}</p>
  {:else if stateKind === 'compared'}
    <div data-testid="compare-result">
      <h4>{activeCheckpointId}</h4>
      <ul>
        {#each Object.entries(compareEntries) as [path, entry] (path)}
          <li>{path}: {describeEntry(entry)}</li>
        {/each}
      </ul>
      <button type="button" onclick={() => { timeline.cancel(); syncFromStore(); }}>
        {$t('checkpoints.back')}
      </button>
    </div>
  {:else if stateKind === 'restore_approval_required'}
    <div role="alertdialog" aria-label={$t('checkpoints.restore_confirm_title')}>
      <p>{$t('checkpoints.restore_confirm_body')}</p>
      <button type="button" onclick={onConfirmRestore}>{$t('checkpoints.restore_confirm_yes')}</button>
      <button type="button" onclick={onCancel}>{$t('checkpoints.restore_confirm_no')}</button>
    </div>
  {:else if stateKind === 'restore_task_approval_required'}
    <div role="alertdialog" aria-label={$t('checkpoints.restore_task_confirm_title')}>
      <p>{$t('checkpoints.restore_task_confirm_body')}</p>
      <button type="button" onclick={onConfirmRestoreTask}>{$t('checkpoints.restore_confirm_yes')}</button>
      <button type="button" onclick={onCancel}>{$t('checkpoints.restore_confirm_no')}</button>
    </div>
  {:else if stateKind === 'restoring'}
    <p role="status">{$t('checkpoints.restoring')}</p>
  {:else if stateKind === 'restoring_task'}
    <p role="status">{$t('checkpoints.restoring')}</p>
  {:else if stateKind === 'restored'}
    <p role="status">{$t('checkpoints.restored')}</p>
  {:else if stateKind === 'restored_task'}
    <p role="status">{$t('checkpoints.restored_task')}</p>
  {:else if stateKind === 'restore_task_conflict'}
    <p role="alert">{$t('checkpoints.restore_task_conflict')}</p>
    <button type="button" onclick={() => { timeline.cancel(); syncFromStore(); }}>
      {$t('checkpoints.back')}
    </button>
  {:else if stateKind === 'conflict'}
    <p role="alert">{$t('checkpoints.conflict')} {message}</p>
    <button type="button" onclick={() => { timeline.cancel(); syncFromStore(); }}>
      {$t('checkpoints.back')}
    </button>
  {/if}
</section>

<style>
  .checkpoint-panel {
    display: block;
  }
  .checkpoint-row {
    border: 1px solid var(--border-subtle, #444);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.5rem;
  }
  .checkpoint-row header {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .checkpoint-task-group h4 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.75rem 0 0.25rem;
  }
  .cp-task-restore {
    font-size: 0.8rem;
    padding: 0.15rem 0.5rem;
  }
  .cp-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0 0.5rem;
    margin: 0.25rem 0 0;
  }
  dt {
    font-weight: 600;
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
</style>
