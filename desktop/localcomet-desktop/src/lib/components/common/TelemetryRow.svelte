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
    <span class="telemetry-label" title={label}>{label}</span>
  </dt>
  <dd class:mono title={String(value)}>{value}</dd>
</div>

<style>
  .telemetry-row {
    display: grid;
    grid-template-columns: var(--telemetry-row-columns, minmax(0, 1fr) minmax(92px, auto));
    align-items: var(--telemetry-row-alignment, center);
    gap: var(--lc-space-3);
    min-height: 42px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  dt {
    display: var(--telemetry-label-display, inline-flex);
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--lc-space-2);
    min-width: 0;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 720;
  }

  .telemetry-label {
    min-width: 0;
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  dd {
    margin: 0;
    min-width: 0;
    max-width: 100%;
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
