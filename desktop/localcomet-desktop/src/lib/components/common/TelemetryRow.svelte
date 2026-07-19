<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  export let label: string;
  export let value: string | number;
  export let tone: StatusTone | string = 'unknown';
  export let mono = false;

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<div class="telemetry-row">
  <dt>
    <StatusDot {tone} label={`${label}: ${value}`} />
    <span>{label}</span>
  </dt>
  <dd class:mono>{value}</dd>
</div>

<style>
  .telemetry-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(92px, auto);
    align-items: center;
    gap: var(--lc-space-3);
    min-height: 42px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  dt {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    min-width: 0;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 720;
  }

  dd {
    margin: 0;
    min-width: 0;
    color: var(--lc-text);
    overflow-wrap: anywhere;
    text-align: right;
    font-size: 12px;
    font-weight: 800;
  }

  .mono {
    font-family: var(--lc-mono);
  }
</style>
