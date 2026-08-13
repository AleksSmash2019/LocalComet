<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import { invoke } from '@tauri-apps/api/core';
  import { t } from '$lib/i18n';

  interface ApprovalRequestPayload {
    request_id: string;
    tool: string;
    risk_level: string;
    target_summary: string;
    side_effect_category: string;
    destructive: boolean;
  }

  let unlisten: UnlistenFn | undefined;
  let currentRequest: ApprovalRequestPayload | null = null;
  let resolving = false;

  onMount(async () => {
    unlisten = await listen<ApprovalRequestPayload>('request_tool_approval', (event) => {
      currentRequest = event.payload;
    });
  });

  onDestroy(() => {
    if (unlisten) unlisten();
  });

  async function resolve(decision: 'approve' | 'reject') {
    if (!currentRequest || resolving) return;
    resolving = true;
    try {
      await invoke('resolve_tool_approval', {
        requestId: currentRequest.request_id,
        decision
      });
    } catch (err) {
      console.error(`Failed to resolve tool approval as ${decision}:`, err);
    } finally {
      resolving = false;
      currentRequest = null;
    }
  }

  function getRiskKey(risk: string): string {
    if (risk === 'read_only') return 'approval.risk_read_only';
    if (risk === 'guarded') return 'approval.risk_guarded';
    if (risk === 'dangerous') return 'approval.risk_dangerous';
    return 'approval.risk_unknown';
  }

  function toSnakeCase(str: string): string {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`).replace(/^_/, '');
  }
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && currentRequest && !resolving) resolve('reject'); }} />

{#if currentRequest}
  <div class="modal-backdrop">
    <div class="modal-content card-surface" role="dialog" aria-modal="true" aria-labelledby="approval-title">
      <h2 id="approval-title">{$t('approval.tool')}: {currentRequest.tool}</h2>
      
      <dl>
        <div>
          <dt>{$t('approval.risk')}</dt>
          <dd class="risk-{currentRequest.risk_level}">{$t(getRiskKey(currentRequest.risk_level))}</dd>
        </div>
        <div>
          <dt>{$t('approval.target')}</dt>
          <dd>{currentRequest.target_summary}</dd>
        </div>
        <div>
          <dt>{$t('approval.side_effects')}</dt>
          <dd>{$t(`approval.side_effects.${toSnakeCase(currentRequest.side_effect_category)}`)}</dd>
        </div>
      </dl>

      {#if currentRequest.destructive}
        <div class="warning-banner">
          ⚠️ {$t('approval.warning_destructive')}
        </div>
      {/if}

      <div class="actions">
        <button type="button" class="btn-reject" disabled={resolving} onclick={() => resolve('reject')}>
          {$t('approval.reject')}
        </button>
        <button type="button" class="btn-approve" disabled={resolving} onclick={() => resolve('approve')}>
          {$t('approval.confirm')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
  }

  .modal-content {
    background: var(--color-panel);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    padding: var(--lc-space-4);
    min-width: 400px;
    max-width: 500px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  h2 {
    margin: 0 0 var(--lc-space-3);
    font-size: 18px;
    color: var(--color-text);
  }

  dl {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-2);
    margin-bottom: var(--lc-space-4);
  }

  div > dt {
    font-size: 12px;
    color: var(--color-muted);
    margin-bottom: 2px;
  }

  div > dd {
    margin: 0;
    font-size: 14px;
    color: var(--color-text);
  }

  .risk-read_only { color: var(--color-info, #3498db); }
  .risk-guarded { color: var(--color-warning, #f39c12); }
  .risk-dangerous { color: var(--color-danger, #e74c3c); font-weight: bold; }

  .warning-banner {
    background: rgba(231, 76, 60, 0.1);
    border-left: 4px solid var(--color-danger, #e74c3c);
    color: var(--color-danger, #e74c3c);
    padding: var(--lc-space-2);
    margin-bottom: var(--lc-space-4);
    font-size: 13px;
    font-weight: 500;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--lc-space-3);
  }

  button {
    padding: var(--lc-space-2) var(--lc-space-4);
    border: none;
    border-radius: var(--lc-radius-sm);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-reject {
    background: transparent;
    border: var(--border-thin);
    color: var(--color-text);
  }
  
  .btn-reject:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.05);
  }

  .btn-approve {
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
  }

  .btn-approve:hover:not(:disabled) {
    opacity: 0.9;
  }
</style>

