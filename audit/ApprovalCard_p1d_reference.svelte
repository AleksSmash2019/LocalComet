<script lang="ts">
  import { t } from '$lib/i18n';
  import { approvalStore, cancelApproval, rejectApproval } from '$lib/stores/approvalStore';
  import type { ApprovalRiskLevel } from '$lib/bridge/approval';

  const ERROR_KEYS: Record<string, string> = {
    approval_required: 'approval.error_approval_required',
    grant_expired: 'approval.error_grant_expired',
    policy_blocked: 'approval.error_policy_blocked'
  };

  const RISK_LABELS: Record<ApprovalRiskLevel, string> = {
    read_only: 'approval.risk_read_only',
    guarded: 'approval.risk_guarded',
    dangerous: 'approval.risk_dangerous'
  };

  function describeExpiry(expiresAtUnixMs: number | null | undefined): string {
    if (!expiresAtUnixMs) return $t('approval.expiry_unknown');
    return new Date(expiresAtUnixMs).toLocaleString();
  }

  function describeRisk(riskLevel: string | undefined): string {
    if (riskLevel === 'read_only' || riskLevel === 'guarded' || riskLevel === 'dangerous') {
      return $t(RISK_LABELS[riskLevel]);
    }
    return $t('approval.risk_unknown');
  }

  let rootEl: HTMLElement;

  function focusOnMount(node: HTMLElement): void {
    node.focus();
  }

  $: state = $approvalStore;
  $: presentation = state.pending?.presentation ?? null;
  $: busy = state.loading;
  $: expired = presentation ? presentation.expiresAtUnixMs <= Date.now() : false;
  $: errorKey = state.errorCode ? (ERROR_KEYS[state.errorCode] ?? 'approval.error_generic') : null;

  function onReject(): void {
    rejectApproval();
  }

  function onCancel(): void {
    cancelApproval();
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelApproval();
      return;
    }
    if (event.key !== 'Tab' || !rootEl) return;
    const focusable = Array.from(rootEl.querySelectorAll<HTMLButtonElement>('button:not([disabled])'));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>

{#if state.pending}
  <div
    class="approval card-surface"
    role="alertdialog"
    aria-modal="true"
    tabindex="-1"
    aria-labelledby="approval-title"
    aria-describedby={presentation?.destructive ? 'approval-destructive' : undefined}
    aria-busy={busy ? 'true' : 'false'}
    bind:this={rootEl}
    on:keydown={onKeydown}
  >
    <div class="approval-summary">
      <span class="status-pill" role="status" aria-live="polite" aria-atomic="true">
        <span class="status-dot"></span>{$t('approval.presenting')}
      </span>
      <h2 id="approval-title">{$t('approval.tool')}: {state.pending.tool}</h2>
      {#if presentation?.destructive}
        <p id="approval-destructive" class="approval-destructive" role="alert">
          {$t('approval.destructive_warning')}
        </p>
      {/if}
      <dl>
        <div>
          <dt>{$t('approval.risk')}</dt>
          <dd>{describeRisk(presentation?.riskLevel)}</dd>
        </div>
        <div>
          <dt>{$t('approval.target')}</dt>
          <dd>{presentation?.targetSummary ? presentation.targetSummary : $t('approval.target_unknown')}</dd>
        </div>
        <div>
          <dt>{$t('approval.side_effects')}</dt>
          <dd>
            {presentation
              ? $t(`approval.side_effects.${presentation.commandFamily}`)
              : $t('approval.side_effects_unknown')}
          </dd>
        </div>
        <div>
          <dt>{$t('approval.expires')}</dt>
          <dd>
            {#if presentation}
              {#if expired}<span class="approval-expired">{$t('approval.expired')}</span> ┬╖ {/if}
              {describeExpiry(presentation.expiresAtUnixMs)}
            {:else}
              {$t('approval.expiry_unknown')}
            {/if}
          </dd>
        </div>
        <div>
          <dt>{$t('approval.scope')}</dt>
          <dd>{presentation?.scopeSummary ? presentation.scopeSummary : $t('approval.scope_unknown')}</dd>
        </div>
      </dl>
      {#if errorKey}
        <p class="approval-error" role="alert">{$t(errorKey)}</p>
      {/if}
    </div>
    <div class="approval-actions">
      <button
        type="button"
        class="approval-reject"
        use:focusOnMount
        on:click={onReject}
        aria-label={$t('approval.reject_action')}
      >
        {$t('approval.reject')}
      </button>
      <button type="button" on:click={onCancel} aria-label={$t('approval.cancel_action')}>
        {$t('approval.cancel')}
      </button>
    </div>
  </div>
{:else}
  <p class="approval-empty">{$t('approval.no_pending')}</p>
{/if}

<style>
  .approval {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-4);
    border-color: var(--lc-line);
    padding: var(--lc-space-4);
  }

  h2 {
    margin: var(--lc-space-3) 0 var(--lc-space-1);
    font-size: 17px;
  }

  .approval-destructive {
    margin: var(--lc-space-2) 0;
    padding: var(--lc-space-2);
    border: var(--border-thin);
    border-color: var(--color-danger, #c0392b);
    border-radius: var(--lc-radius-sm);
    color: var(--color-danger, #c0392b);
    font-weight: 600;
  }

  .approval-error {
    margin: 0;
    color: var(--color-danger, #c0392b);
  }

  .approval-expired {
    color: var(--color-danger, #c0392b);
    font-weight: 600;
  }

  .approval-empty {
    margin: 0;
    color: var(--color-muted);
  }

  .approval-actions {
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
  }

  button {
    min-width: 88px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--color-panel);
    color: var(--color-muted);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  button:focus-visible {
    outline: 2px solid var(--color-accent, #2f6fed);
    outline-offset: 2px;
  }
</style>
