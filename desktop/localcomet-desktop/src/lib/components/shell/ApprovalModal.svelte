<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import { invoke } from '@tauri-apps/api/core';
  import { get } from 'svelte/store';
  import { t } from '$lib/i18n';
  import {
    approvalPrompt,
    clearApprovalPrompt,
    rejectActiveApproval,
    setApprovalPrompt,
    type ActiveApprovalPrompt
  } from '$lib/stores/approvalStore';

  // The Rust prompt denies issuance after its own 120s timeout; mirror that
  // client-side so an ignored card does not outlive the server-side rejection.
  const PROMPT_TIMEOUT_MS = 120_000;

  let unlisten: UnlistenFn | undefined;
  let destroyed = false;
  let currentRequest: ActiveApprovalPrompt | null = null;
  let resolving = false;
  let resolutionError = "";
  let dismissTimer: ReturnType<typeof setTimeout> | undefined;

  function clearDismissTimer(): void {
    if (dismissTimer) {
      clearTimeout(dismissTimer);
      dismissTimer = undefined;
    }
  }

  onMount(() => {
    let active = true;
    const stopPromptSync = approvalPrompt.subscribe((prompt) => {
      currentRequest = prompt;
      if (!prompt) {
        clearDismissTimer();
        resolving = false;
      }
    });
    listen<ActiveApprovalPrompt>('request_tool_approval', (event) => {
      setApprovalPrompt(event.payload);
      clearDismissTimer();
      dismissTimer = setTimeout(() => {
        void rejectActiveApproval();
      }, PROMPT_TIMEOUT_MS);
    }).then((unlistenFn) => {
      if (!active || destroyed) {
        unlistenFn();
      } else {
        unlisten = unlistenFn;
      }
    }).catch((err) => {
      console.error('Failed to register tool approval listener:', err);
    });

    return () => {
      active = false;
      stopPromptSync();
    };
  });

  onDestroy(() => {
    destroyed = true;
    clearDismissTimer();
    void rejectActiveApproval();
    if (unlisten) {
      unlisten();
      unlisten = undefined;
    }
  });

      async function resolve(decision: 'approve' | 'reject') {
    if (!currentRequest || resolving) return;
    resolutionError = '';
    resolving = true;
    clearDismissTimer();
    try {
      await invoke('resolve_tool_approval', {
        requestId: currentRequest.request_id,
        decision
      });
    } catch (err) {
      console.error(`Failed to resolve tool approval as ${decision}:`, err);
      resolutionError = get(t)('approval.resolve_error');

    } finally {
      resolving = false;
      if (!resolutionError) {
        clearApprovalPrompt();
      }
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

  function formatTargetSummary(summary: string): string {
    try {
      const parsed = JSON.parse(summary);
      if (typeof parsed === 'object' && parsed !== null) {
        return JSON.stringify(parsed, null, 2);
      }
      return summary;
    } catch {
      return summary;
    }
  }

  function formatExpiry(expiresAtUnixMs: number | undefined): string {
    if (typeof expiresAtUnixMs !== 'number' || !Number.isFinite(expiresAtUnixMs) || expiresAtUnixMs <= 0) {
      return get(t)('approval.expiry_unknown');
    }
    return new Date(expiresAtUnixMs).toLocaleTimeString();
  }
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && currentRequest && !resolving) resolve('reject'); }} />

{#if currentRequest}
  <div class="modal-backdrop">
    <div
      class="modal-content card-surface"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-title"
      data-approval-request-id={currentRequest.request_id}
      data-model-request-id={currentRequest.model_request_id ?? ''}
      data-model-action-id={currentRequest.model_action_id ?? ''}
    >
      <h2 id="approval-title">{$t('approval.tool')}: {currentRequest.tool}</h2>
      
      <dl>
        <div>
          <dt>{$t('approval.risk')}</dt>
          <dd class="risk-{currentRequest.risk_level}">{$t(getRiskKey(currentRequest.risk_level))}</dd>
        </div>
        <div class="target-section">
          <dt>{$t('approval.target')}</dt>
          <dd class="target-summary">{formatTargetSummary(currentRequest.target_summary)}</dd>
        </div>
        <div>
          <dt>{$t('approval.side_effects')}</dt>
          <dd>{$t(`approval.side_effects.${toSnakeCase(currentRequest.side_effect_category)}`)}</dd>
        </div>
        <div>
          <dt>{$t('approval.expires')}</dt>
          <dd>{formatExpiry(currentRequest.expires_at_unix_ms)}</dd>
        </div>
      </dl>

      {#if currentRequest.risk_level === 'dangerous'}
        <div class="warning-banner">
          ⚠️ {$t(currentRequest.destructive ? 'approval.warning_destructive' : 'approval.warning_sensitive')}
        </div>
      {/if}

      {#if resolutionError}
        <div class="approval-error" role="alert" aria-live="assertive">{$t('approval.resolve_error_prefix')} {resolutionError}</div>
      {/if}
      <div class="actions">
        <button type="button" class="btn-reject" disabled={resolving} on:click={() => resolve('reject')}>
          {$t('approval.reject')}
        </button>
        <button type="button" class="btn-approve" disabled={resolving} on:click={() => resolve('approve')}>
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

  .target-summary {
    white-space: pre-wrap;
    font-family: monospace;
    background: rgba(255, 255, 255, 0.05);
    padding: var(--lc-space-2);
    border-radius: var(--lc-radius-sm);
    word-break: break-all;
    margin-top: 4px;
  }

  .risk-read_only { color: var(--lc-info); }
  .risk-guarded { color: var(--lc-warning); }
  .risk-dangerous { color: var(--lc-danger); font-weight: bold; }

  .warning-banner {
    background: color-mix(in srgb, var(--lc-danger) 12%, transparent);
    border-left: 4px solid var(--lc-danger);
    color: var(--lc-danger);
    padding: var(--lc-space-2);
    margin-bottom: var(--lc-space-4);
    font-size: 13px;
    font-weight: 500;
  }

  .approval-error {
    margin: 0.75rem 0;
    padding: 0.65rem 0.8rem;
    color: #ffd7d7;
    background: rgba(180, 35, 35, 0.22);
    border: 1px solid rgba(255, 120, 120, 0.55);
    border-radius: 0.4rem;
    white-space: pre-wrap;
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

