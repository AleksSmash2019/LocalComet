<script lang="ts">
  import EventStream from '$lib/components/common/EventStream.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { managedRuntimeStore, refreshManagedRuntimeStatus } from '$lib/stores/modelGateway';

  let refreshing = false;

  async function refresh(): Promise<void> {
    refreshing = true;
    try {
      await refreshManagedRuntimeStatus();
    } finally {
      refreshing = false;
    }
  }
</script>

<section class="observability" aria-labelledby="observability-title">
  <div class="heading">
    <div>
      <span class="eyebrow">{$t('observability.eyebrow')}</span>
      <h3 id="observability-title">{$t('observability.title')}</h3>
      <p>{$t('observability.subtitle')}</p>
    </div>
    <button type="button" disabled={refreshing} onclick={() => void refresh()}>
      <Icon name="refresh" size={15} />
      {$t(refreshing ? 'observability.refreshing' : 'observability.refresh')}
    </button>
  </div>

  <div class="notice">
    <Icon name="shield" size={18} />
    <p>{$t('observability.boundary')}</p>
  </div>

  <div class="summary">
    <div>
      <span>{$t('observability.control_events')}</span>
      <strong>{$controlPlaneStore.recentEvents.length}</strong>
    </div>
    <div>
      <span>{$t('observability.runtime_state')}</span>
      <StatusBadge
        label={$managedRuntimeStore.status?.state ?? $t('common.not_determined')}
        tone={$managedRuntimeStore.status?.state === 'Ready' ? 'ready' : 'unknown'}
      />
    </div>
    <div>
      <span>{$t('observability.runtime_lines')}</span>
      <strong>{$managedRuntimeStore.logs.stdout_tail.length + $managedRuntimeStore.logs.stderr_tail.length}</strong>
    </div>
  </div>

  <div class="room-grid">
    <article>
      <header>
        <h4>{$t('observability.validated_events')}</h4>
        <span>{$t('observability.session_only')}</span>
      </header>
      <EventStream events={$controlPlaneStore.recentEvents} />
    </article>

    <article>
      <header>
        <h4>{$t('observability.runtime_logs')}</h4>
        <span>{$t('observability.sanitized_tail')}</span>
      </header>
      {#if $managedRuntimeStore.logs.stdout_tail.length === 0 && $managedRuntimeStore.logs.stderr_tail.length === 0}
        <p class="empty">{$t('observability.no_runtime_logs')}</p>
      {:else}
        <ol class="log-lines">
          {#each $managedRuntimeStore.logs.stderr_tail as line}
            <li class="stderr"><span>stderr</span><code>{line}</code></li>
          {/each}
          {#each $managedRuntimeStore.logs.stdout_tail as line}
            <li><span>stdout</span><code>{line}</code></li>
          {/each}
        </ol>
      {/if}
    </article>
  </div>
</section>

<style>
  .observability { display: grid; gap: var(--lc-space-4); }
  .heading, .heading button, .notice, .summary > div, article header { display: flex; align-items: center; }
  .heading { align-items: flex-start; justify-content: space-between; gap: var(--lc-space-3); }
  .heading > div { min-width: 0; }
  .eyebrow { color: var(--lc-accent); font-family: var(--lc-mono); font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h3, h4, p { margin: 0; }
  h3 { margin-top: var(--lc-space-1); color: var(--lc-text); font-size: 20px; text-transform: none; letter-spacing: -.02em; }
  .heading p, .notice p { margin-top: var(--lc-space-1); color: var(--lc-muted); font-size: 12px; line-height: 1.5; }
  .heading button { flex: 0 0 auto; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: 0 var(--lc-space-3); background: var(--lc-panel-soft); cursor: pointer; }
  .notice { align-items: flex-start; gap: var(--lc-space-2); border: 1px solid var(--lc-line-strong); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-accent-dim); color: var(--lc-accent); }
  .notice p { margin: 0; color: var(--lc-text); }
  .summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--lc-space-2); }
  .summary > div { min-width: 0; justify-content: space-between; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  .summary span { color: var(--lc-muted); font-size: 11px; }
  .summary strong { color: var(--lc-text); font-family: var(--lc-mono); font-size: 14px; }
  .room-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--lc-space-3); }
  article { min-width: 0; border: var(--border-thin); border-radius: var(--lc-radius-md); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  article header { justify-content: space-between; gap: var(--lc-space-2); margin-bottom: var(--lc-space-3); }
  h4 { font-size: 12px; }
  article header span { color: var(--lc-faint); font-family: var(--lc-mono); font-size: 10px; }
  .log-lines { display: grid; max-height: 360px; overflow: auto; gap: var(--lc-space-1); margin: 0; padding: 0; list-style: none; }
  .log-lines li { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: var(--lc-space-2); border-bottom: var(--border-thin); padding: var(--lc-space-2); }
  .log-lines span { color: var(--lc-info); font-family: var(--lc-mono); font-size: 10px; }
  .log-lines .stderr span { color: var(--lc-warning); }
  code { min-width: 0; overflow-wrap: anywhere; color: var(--lc-muted); font-family: var(--lc-mono); font-size: 10px; white-space: pre-wrap; }
  .empty { border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); color: var(--lc-muted); font-size: 12px; }
  @media (max-width: 720px) { .summary, .room-grid { grid-template-columns: 1fr; } .heading { flex-direction: column; } }
</style>
