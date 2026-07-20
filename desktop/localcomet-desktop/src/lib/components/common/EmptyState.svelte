<script lang="ts">
  import LocalCometLogo from './LocalCometLogo.svelte';

  export let title: string;
  export let detail: string;
  export let actionLabel: string | undefined = undefined;
  export let onAction: (() => void) | undefined = undefined;
  export let busy = false;
  export let statusLabel: string | undefined = undefined;
</script>

<div class="empty-state" aria-busy={busy} aria-live="polite">
  <LocalCometLogo size={42} labelled={false} />
  <div>
    <h2>{title}</h2>
    <p>{detail}</p>
    {#if statusLabel}
      <span class:busy class="state-label">{statusLabel}</span>
    {/if}
    {#if actionLabel && onAction}
      <button type="button" class="primary-button" onclick={onAction}>
        {actionLabel}
      </button>
    {/if}
  </div>
</div>

<style>
  .empty-state {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-4);
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  p {
    margin-top: var(--lc-space-1);
    color: var(--lc-muted);
  }

  .primary-button {
    margin-top: var(--lc-space-3);
    min-height: 36px;
    padding: 0 var(--lc-space-4);
    border: none;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 800;
    font-size: 13px;
    cursor: pointer;
  }

  .primary-button:hover {
    background: var(--lc-accent-strong);
  }

  .state-label {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
  }

  .state-label.busy::before {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--lc-accent);
    content: '';
  }
</style>
