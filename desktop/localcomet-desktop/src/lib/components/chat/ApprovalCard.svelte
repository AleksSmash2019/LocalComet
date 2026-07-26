<script lang="ts">
  import type { ApprovalMock } from '$lib/data/mockData';
  import { t } from '$lib/i18n';

  export let item: ApprovalMock;
</script>

<article class="approval card-surface" aria-label={$t('approval.section_aria')}>
  <div>
    <span class="status-pill"><span class="status-dot disabled"></span>{$t('approval.disabled')}</span>
    <h2>{item.title}</h2>
    <p>{item.detail}</p>
  </div>
  <div class="approval-actions">
    <button type="button" disabled aria-label={$t('approval.confirm_aria')}>{$t('approval.confirm')}</button>
    <button type="button" disabled aria-label={$t('approval.reject_aria')}>{$t('approval.reject')}</button>
  </div>
</article>

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

  p {
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
    cursor: not-allowed;
  }
</style>
