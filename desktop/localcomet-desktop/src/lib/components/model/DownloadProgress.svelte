<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';

  export let title: string;
  export let detail: string = '';
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
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
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
    color: #f8fafc;
    letter-spacing: 0.02em;
  }

  .progress-detail {
    font-size: 13px;
    color: #94a3b8;
  }

  .progress-percent {
    font-size: 16px;
    font-weight: 700;
    color: #10b981;
    font-variant-numeric: tabular-nums;
  }

  .progress-track {
    height: 6px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    position: relative;
    overflow: visible;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #34d399, #10b981);
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
    background: #10b981;
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
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #f87171;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .cancel-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.4);
    color: #fca5a5;
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
