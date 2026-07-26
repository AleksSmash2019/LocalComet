<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  export let label: string;
  export let tone: StatusTone | string = 'unknown';

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<span class="status-badge tone-{tone}">
  <StatusDot {tone} {label} />
  <span>{label}</span>
</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    min-height: 24px;
    border: var(--border-thin);
    border-radius: 999px;
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: 2px 10px;
    font-size: 11.5px;
    font-weight: 500;
    white-space: nowrap;
  }

  .tone-ready {
    border-color: color-mix(in srgb, var(--lc-accent) 30%, transparent);
    background: color-mix(in srgb, var(--lc-accent) 12%, transparent);
    color: var(--lc-accent);
  }

  .tone-info {
    border-color: color-mix(in srgb, var(--lc-info) 30%, transparent);
    background: color-mix(in srgb, var(--lc-info) 12%, transparent);
    color: var(--lc-info);
  }

  .tone-waiting {
    border-color: color-mix(in srgb, var(--lc-warning) 30%, transparent);
    background: color-mix(in srgb, var(--lc-warning) 12%, transparent);
    color: var(--lc-warning);
  }

  .tone-danger {
    border-color: color-mix(in srgb, var(--lc-danger) 30%, transparent);
    background: color-mix(in srgb, var(--lc-danger) 12%, transparent);
    color: var(--lc-danger);
  }
</style>
