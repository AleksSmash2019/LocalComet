<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  export let label: string;
  export let tone: StatusTone | string = 'unknown';

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<span class="status-badge">
  <StatusDot {tone} {label} />
  <span>{label}</span>
</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    min-height: 28px;
    border: var(--border-thin);
    border-radius: 999px;
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: 0 var(--lc-space-3);
    font-size: 12px;
    font-weight: 760;
    white-space: nowrap;
  }
</style>
