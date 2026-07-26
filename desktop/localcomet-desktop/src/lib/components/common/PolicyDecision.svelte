<script lang="ts">
  import LocalCometSecurityEmblem from './LocalCometSecurityEmblem.svelte';
  import StatusBadge from './StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import type { RiskLevel } from '$lib/risk';
  import { RISK_LABEL_KEY, RISK_TONE } from '$lib/risk';

  export let risk: RiskLevel | undefined = undefined;
</script>

<section class="policy-decision" aria-label={$t('diag.policy_decision_label')}>
  <LocalCometSecurityEmblem size={34} labelled={false} />
  <div>
    <h3>{$t('diag.policy_decision')}</h3>
    {#if risk}
      <StatusBadge label={$t(RISK_LABEL_KEY[risk])} tone={RISK_TONE[risk]} />
    {:else}
      <StatusBadge label={$t('diag.not_evaluated')} tone="unknown" />
    {/if}
  </div>
</section>

<style>
  .policy-decision {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-3);
  }

  h3 {
    margin: 0 0 var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 12px;
    text-transform: uppercase;
  }
</style>