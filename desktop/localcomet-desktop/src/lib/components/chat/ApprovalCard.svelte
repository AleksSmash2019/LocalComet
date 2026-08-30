<script lang="ts">
  import { t } from '$lib/i18n';
  import { approvalStore, confirmApproval, rejectApproval } from '$lib/stores/approvalStore';
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

  function describeInput(input: unknown): string {
    if (input && typeof input === 'object' && !Array.isArray(input)) {
      const record = input as Record<string, unknown>;
      if (typeof record.path === 'string') return record.path;
      if (typeof record.modelId === 'string') return record.modelId;
      if (typeof record.tool === 'string') return record.tool;
    }
    return $t('approval.target_unknown');
  }

  function describeExpiry(expiresAtUnixMs: number | null | undefined): string {
    if (!expiresAtUnixMs) return $t('approval.expiry_unknown');
    const when = new Date(expiresAtUnixMs);
    return when.toLocaleString();
  }

  function describeSideEffects(input: unknown, commandFamily: string | undefined, riskLevel: string | undefined): string {
    if (commandFamily !== 'computer_use') {
      return commandFamily ? $t(`approval.side_effects.${commandFamily}`) : $t('approval.side_effects_unknown');
    }
    if (riskLevel === 'dangerous') return $t('approval.side_effects.computer_use_sensitive_or_external_effect');
    const action = input && typeof input === 'object' && !Array.isArray(input)
      ? String((input as Record<string, unknown>).action ?? '').toLowerCase()
      : '';
    const keyByAction: Record<string, string> = {
      screenshot: 'approval.side_effects.computer_use_observation',
      wait: 'approval.side_effects.computer_use_observation',
      observe: 'approval.side_effects.computer_use_observation',
      mouse_move: 'approval.side_effects.computer_use_observation',
      scroll: 'approval.side_effects.computer_use_observation',
      open_app: 'approval.side_effects.computer_use_application_launch',
      open_folder: 'approval.side_effects.computer_use_folder_open'
    };
    return $t(keyByAction[action] ?? 'approval.side_effects.computer_use_ui_interaction');
  }

  function describeRisk(riskLevel: string | undefined): string {
    if (riskLevel === 'read_only' || riskLevel === 'guarded' || riskLevel === 'dangerous') {
      return $t(RISK_LABELS[riskLevel]);
    }
    return $t('approval.risk_unknown');
  }

  $: state = $approvalStore;
  $: busy = state.phase === 'requesting' || state.phase === 'executing';
  $: phaseKey =
    state.phase === 'requesting'
      ? 'approval.requesting'
      : state.phase === 'executing'
        ? 'approval.executing'
        : 'approval.pending';
  $: errorKey = state.errorCode ? (ERROR_KEYS[state.errorCode] ?? 'approval.error_generic') : null;
  $: approval = state.pending?.envelope ?? null;

  async function onConfirm(): Promise<void> {
    await confirmApproval();
  }
  function onReject(): void {
    rejectApproval();
  }
</script>

{#if state.pending}
  <article
    class="approval card-surface"
    aria-label={$t('approval.section_aria')}
    data-testid="approval-card"
    data-lc="approval-card"
    data-approval-id={approval?.approvalId ?? ''}
    data-approval-authority="legacy-compatibility"
    data-input-digest={state.pending.inputDigest ?? ''}
  >
    <div class="approval-summary">
      <span class="status-pill"><span class="status-dot"></span>{$t(phaseKey)}</span>
      <h2>{$t('approval.tool')}: {state.pending.tool}</h2>
      <dl>
        <div>
          <dt>{$t('approval.risk')}</dt>
          <dd>{describeRisk(approval?.riskLevel)}</dd>
        </div>
        <div>
          <dt>{$t('approval.target')}</dt>
          <dd>{describeInput(state.pending.input)}</dd>
        </div>
        <div>
          <dt>{$t('approval.side_effects')}</dt>
          <dd>{describeSideEffects(state.pending.input, approval?.commandFamily, approval?.riskLevel)}</dd>
        </div>
        <div>
          <dt>{$t('approval.expires')}</dt>
          <dd>{describeExpiry(approval?.expiresAtUnixMs)}</dd>
        </div>
      </dl>
      {#if errorKey}
        <p class="approval-error">{$t(errorKey)}</p>
      {/if}
    </div>
    <div class="approval-actions">
      <button type="button" data-testid="approval-confirm" data-lc="approval-confirm" disabled={busy} onclick={onConfirm} aria-label={$t('approval.confirm')}>
        {$t('approval.confirm')}
      </button>
      <button type="button" data-testid="approval-reject" data-lc="approval-reject" disabled={busy} onclick={onReject} aria-label={$t('approval.reject')}>
        {$t('approval.reject')}
      </button>
    </div>
  </article>
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

  .approval-error {
    margin: 0;
    color: var(--lc-danger);
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
</style>
