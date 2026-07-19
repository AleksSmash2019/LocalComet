<script lang="ts">
  import LocalCometSecurityEmblem from './LocalCometSecurityEmblem.svelte';
  import StatusBadge from './StatusBadge.svelte';
  import { t } from '$lib/i18n';
</script>

<section class="policy-decision" aria-label={$t('diag.policy_decision_label')}>
  <LocalCometSecurityEmblem size={34} labelled={false} />
  <div>
    <h3>{$t('diag.policy_decision')}</h3>
    <StatusBadge label={$t('diag.not_evaluated')} tone="unknown" />
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
