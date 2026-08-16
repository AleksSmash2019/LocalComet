<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';

  export let title: string;
  export let detail: string = '';
  export let phase: string = '';
  export let percent: number | null = null;
  export let onCancel: (() => void) | null = null;
</script>

<div class="premium-progress-panel" role="status" aria-live="polite">
  <div class="progress-header">
    <div class="progress-text">
      <strong>{title}</strong>
      {#if detail}
        <span class="progress-detail">{detail}</span>
      {/if}
      {#if phase}
        <span class="progress-phase">{phase}</span>
      {/if}
    </div>
    {#if percent !== null}
      <span class="progress-percent">{percent}%</span>
    {/if}
  </div>

  <div class="progress-track">
    {#if percent !== null}
      <div class="progress-fill" style="width: {percent}%;"></div>
    {:else}
      <div class="progress-fill indeterminate"></div>
    {/if}
    <div class="progress-glow" style={percent !== null ? `width: ${percent}%;` : 'width: 100%;'}></div>
  </div>

  {#if onCancel}
    <button type="button" class="cancel-btn" onclick={onCancel} aria-label="Отменить">
      <Icon name="cancel" size={16} />
      <span>Отменить</span>
    </button>
  {/if}
</div>

<style>
  .premium-progress-panel {
    background: var(--lc-panel);
    border: 1px solid var(--lc-line);
    border-radius: var(--radius-3);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: var(--lc-shadow-e2);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    position: relative;
    overflow: hidden;
    width: 100%;
    margin-top: 16px;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }

  .progress-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .progress-text strong {
    font-size: 14px;
    font-weight: 600;
    color: var(--lc-text);
    letter-spacing: 0.02em;
  }

  .progress-detail {
    font-size: 13px;
    color: var(--lc-muted);
  }

  .progress-phase {
    font-size: 12px;
    color: var(--lc-accent-strong);
    font-weight: 600;
    letter-spacing: 0.02em;
    animation: phasePulse 2s ease-in-out infinite;
  }

  @keyframes phasePulse {
    0%, 100% { opacity: 0.7; }
    50% { opacity: 1; }
  }

  .progress-percent {
    font-size: 16px;
    font-weight: 700;
    color: var(--lc-accent);
    font-variant-numeric: tabular-nums;
  }

  .progress-track {
    height: 6px;
    background: color-mix(in srgb, var(--lc-line) 50%, transparent);
    border-radius: 6px;
    position: relative;
    overflow: visible;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--lc-accent-strong), var(--lc-accent));
    border-radius: 6px;
    transition: width 0.3s ease-out;
    position: relative;
    z-index: 2;
  }

  .progress-fill.indeterminate {
    width: 30%;
    animation: indeterminate 1.5s infinite ease-in-out;
  }

  .progress-glow {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    background: var(--lc-accent);
    filter: blur(8px);
    opacity: 0.6;
    border-radius: 6px;
    z-index: 1;
    transition: width 0.3s ease-out;
  }

  .progress-fill.indeterminate + .progress-glow {
    width: 30% !important;
    animation: indeterminate 1.5s infinite ease-in-out;
  }

  .cancel-btn {
    align-self: flex-start;
    display: flex;
    align-items: center;
    gap: 6px;
    background: color-mix(in srgb, var(--lc-danger) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--lc-danger) 25%, transparent);
    color: var(--lc-danger);
    padding: 6px 12px;
    border-radius: var(--radius-1);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .cancel-btn:hover {
    background: color-mix(in srgb, var(--lc-danger) 22%, transparent);
    border-color: color-mix(in srgb, var(--lc-danger) 45%, transparent);
    color: var(--lc-text);
  }

  @keyframes indeterminate {
    0% {
      left: -30%;
    }
    100% {
      left: 100%;
    }
  }
</style>
