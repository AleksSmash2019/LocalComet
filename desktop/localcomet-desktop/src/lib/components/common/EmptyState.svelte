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
    border-color: color-mix(in srgb, var(--lc-line) 84%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-panel-solid) 50%, transparent);
    padding: 20px;
    animation: empty-in 400ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 14px;
    font-weight: 700;
  }

  p {
    margin-top: var(--lc-space-1);
    color: var(--lc-muted);
    font-size: 13px;
    line-height: 1.55;
  }

  .primary-button {
    margin-top: var(--lc-space-3);
    min-height: 32px;
    padding: 0 12px;
    border: none;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 650;
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

  @keyframes empty-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
