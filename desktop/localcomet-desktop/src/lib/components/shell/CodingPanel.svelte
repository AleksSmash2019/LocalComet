<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n';
  import {
    CodingTaskStore,
    fetchLspDiagnostics,
    type LspDiagnosticsResponse,
    type PersistedCodingTask
  } from '$lib/stores/codingTask';
  import { errorDisplayText, type NormalizedError } from '$lib/errors/normalizedError';

  let store = new CodingTaskStore();
  let statusLabel = 'idle';
  let outcomeKey = '';
  let reason = '';
  let lastError: NormalizedError | null = null;
  let events: ReadonlyArray<{ seq: number; event_type: string; state_after: string }> = [];
  let workspacePath = '';
  let relPath = 'calc.rs';
  let newContent = '';
  let lspBusy = false;
  let lspResult: LspDiagnosticsResponse | null = null;
  let lspError = '';
  let persistedTasks: readonly PersistedCodingTask[] = [];
  let recoveryBusy = false;

  /** Outcome vocabulary is i18n-rendered; unknown stays machine-readable. */
  const OUTCOME_KEYS: Record<string, string> = {
    completed: 'coding.outcome.behavior_verified',
    compile_verified_only: 'coding.outcome.compile_verified_only',
    failed: 'coding.outcome.failed',
    blocked: 'coding.outcome.blocked',
    cancelled: 'coding.outcome.cancelled',
    paused_for_review: 'coding.outcome.paused_for_review'
  };

  function sync(): void {
    statusLabel = typeof store.status === 'string' ? store.status : 'failed';
    outcomeKey = OUTCOME_KEYS[statusLabel] ?? '';
    reason = typeof store.status === 'string' ? (store.lastResult?.reason ?? store.recoveryReason) : store.status.error;
    lastError = store.lastError;
    events = store.events;
    persistedTasks = store.persistedTasks;
  }

  async function onRefreshTasks(): Promise<void> {
    await store.refreshPersistedTasks();
    sync();
  }

  async function onRecover(taskId: string): Promise<void> {
    if (recoveryBusy) return;
    recoveryBusy = true;
    try {
      await store.recover(taskId);
      sync();
    } finally {
      recoveryBusy = false;
    }
  }

  async function onStart(): Promise<void> {
    await store.start(workspacePath, relPath, newContent);
    sync();
    await store.refreshEvents();
    await store.refreshPersistedTasks();
    sync();
  }

  async function onCancel(): Promise<void> {
    await store.cancel();
    sync();
  }

  onMount(() => {
    void onRefreshTasks();
  });

  /** Real LSP probe through the typed Rust seam; unavailable is truthful. */
  async function onLspCheck(): Promise<void> {
    if (lspBusy || !workspacePath || !relPath) return;
    lspBusy = true;
    lspError = '';
    try {
      lspResult = await fetchLspDiagnostics(workspacePath, relPath);
    } catch (error) {
      lspResult = null;
      lspError = errorDisplayText(error);
    } finally {
      lspBusy = false;
    }
  }
</script>

<section aria-labelledby="coding-title" class="coding-panel">
  <h3 id="coding-title">{$t('coding.title')}</h3>

  <section class="persisted-tasks" aria-labelledby="coding-persisted-title">
    <header class="persisted-header">
      <h4 id="coding-persisted-title">{$t('coding.persisted_title')}</h4>
      <button type="button" onclick={onRefreshTasks} disabled={recoveryBusy}>{$t('coding.refresh')}</button>
    </header>
    <p class="persisted-note">{$t('coding.persisted_note')}</p>
    {#if persistedTasks.length > 0}
      <ul class="persisted-list">
        {#each persistedTasks as task (task.task_id)}
          <li>
            <code>{task.task_id}</code>
            <span data-testid="coding-persisted-status">{task.status}</span>
            {#if task.last_seq !== undefined}<small>#{task.last_seq}</small>{/if}
            <button type="button" onclick={() => onRecover(task.task_id)} disabled={recoveryBusy}>
              {$t('coding.recover')}
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="persisted-empty">{$t('coding.persisted_empty')}</p>
    {/if}
  </section>

  <label class="field">
    <span>{$t('coding.workspace')}</span>
    <input bind:value={workspacePath} placeholder="C:\projects\fixture" />
  </label>
  <label class="field">
    <span>{$t('coding.file')}</span>
    <input bind:value={relPath} />
  </label>
  <label class="field">
    <span>{$t('coding.content')}</span>
    <textarea bind:value={newContent} rows="4"></textarea>
  </label>

  <div class="actions">
    <button type="button" onclick={onStart} disabled={statusLabel === 'starting'}>
      {$t('coding.start')}
    </button>
    <button
      type="button"
      onclick={onCancel}
      disabled={statusLabel !== 'starting'}
    >
      {$t('coding.cancel')}
    </button>
  </div>

  <p role="status" data-testid="coding-status">
    {$t('coding.state_prefix')}
    {#if outcomeKey}
      {$t(outcomeKey)}
    {:else}
      {statusLabel}
    {/if}
    {#if reason}
      — {reason}
    {/if}
  </p>

  {#if lastError}
    <p class="diag" data-testid="coding-error-diag">
      {$t('coding.error_diag')} {lastError.code} · {lastError.phase ?? '—'} · {lastError.correlationId ?? '—'}
    </p>
  {/if}

  {#if events.length > 0}
    <h4>{$t('coding.events')}</h4>
    <ol class="events" data-testid="coding-events">
      {#each events as e (e.seq)}
        <li>{e.seq}. {e.event_type} → {e.state_after}</li>
      {/each}
    </ol>
  {/if}

  <div class="lsp">
    <h4>{$t('coding.lsp_title')}</h4>
    <button type="button" onclick={onLspCheck} disabled={lspBusy || !workspacePath || !relPath}>
      {$t('coding.lsp_check')}
    </button>
    {#if lspResult}
      <p data-testid="coding-lsp-result">
        {#if lspResult.available}
          {$t('coding.lsp_available')} · {lspResult.diagnostics?.length ?? 0}
        {:else}
          {$t('coding.lsp_unavailable')} — {lspResult.reason}
        {/if}
      </p>
      {#if lspResult.available && (lspResult.diagnostics?.length ?? 0) > 0}
        <ul class="diags" data-testid="coding-lsp-diagnostics">
          {#each lspResult.diagnostics ?? [] as d}
            <li>[{d.severity}] {d.file}:{d.line + 1}:{d.column + 1} {d.message}</li>
          {/each}
        </ul>
      {/if}
    {:else if lspError}
      <p class="diag" data-testid="coding-lsp-error">{lspError}</p>
    {/if}
  </div>
</section>

<style>
  .persisted-tasks {
    margin-bottom: 0.85rem;
    border: 1px solid color-mix(in srgb, var(--lc-line) 70%, transparent);
    border-radius: var(--lc-radius-md);
    padding: 0.75rem;
    background: var(--lc-panel-soft);
  }
  .persisted-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .persisted-header h4,
  .persisted-note,
  .persisted-empty {
    margin: 0;
  }
  .persisted-note,
  .persisted-empty {
    color: var(--lc-muted);
    font-size: 0.8rem;
  }
  .persisted-list {
    display: grid;
    gap: 0.35rem;
    margin: 0.65rem 0 0;
    padding: 0;
    list-style: none;
  }
  .persisted-list li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto auto;
    align-items: center;
    gap: 0.45rem;
  }
  .persisted-list code,
  .persisted-list small {
    overflow-wrap: anywhere;
    font-family: monospace;
  }
  .persisted-list span {
    color: var(--lc-info);
    font-size: 0.78rem;
  }
  .field {
    display: block;
    margin-bottom: 0.5rem;
  }
  .field input,
  .field textarea {
    width: 100%;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  .diag {
    font-family: monospace;
    font-size: 0.8rem;
    opacity: 0.75;
  }
  .lsp {
    margin-top: 0.75rem;
  }
  .diags {
    font-family: monospace;
    font-size: 0.8rem;
    padding-left: 1rem;
  }
</style>
