<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  $: validationTone =
    review.validation.outcome === 'VALID'
      ? 'ready'
      : review.validation.outcome === 'STALE'
        ? 'waiting'
        : 'danger';
</script>

<section class="review-panel" aria-labelledby="review-validation-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.validation.eyebrow')}</p>
      <h2 id="review-validation-heading">{$t('review.validation.title')}</h2>
    </div>
    <StatusBadge
      label={$t(`review.validation.outcome.${review.validation.outcome}`)}
      tone={validationTone}
    />
  </header>

  <dl class="validation-grid">
    <div>
      <dt>{$t('review.validation.contract')}</dt>
      <dd><code>{review.validation.contractVersion}</code></dd>
    </div>
    <div>
      <dt>{$t('review.validation.content_hash')}</dt>
      <dd><code>{review.validation.proposalContentHash}</code></dd>
    </div>
    <div>
      <dt>{$t('review.validation.validated_revision')}</dt>
      <dd><code>{review.validation.validatedVaultRevision}</code></dd>
    </div>
    <div>
      <dt>{$t('review.validation.snapshot')}</dt>
      <dd>{review.validation.snapshotSummary}</dd>
    </div>
  </dl>

  {#if review.validation.snapshotTruncated}
    <p class="truncation-notice">
      {$t('review.validation.snapshot_truncated')}
    </p>
  {/if}

  <section class="source-findings" aria-labelledby="review-source-findings-heading">
    <h3 id="review-source-findings-heading">{$t('review.validation.source_findings')}</h3>
    {#if review.validation.sourceFindings.length === 0}
      <p>{$t('review.none')}</p>
    {:else}
      <ul>
        {#each review.validation.sourceFindings as sourceFinding}
          <li>
            <code>{sourceFinding[0]}</code>
            <span>{sourceFinding[1]}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-4);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  h3 {
    font-size: 13px;
  }

  .validation-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-3);
    margin: 0;
  }

  .validation-grid > div {
    min-width: 0;
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    margin-bottom: 6px;
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 720;
  }

  dd {
    min-width: 0;
    overflow-wrap: anywhere;
    margin: 0;
    color: var(--lc-text);
    font-size: 12px;
    line-height: 1.5;
  }

  code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .truncation-notice {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 38%, transparent);
    border-radius: var(--lc-radius-sm);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  .source-findings {
    margin-top: var(--lc-space-4);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-3);
  }

  .source-findings p {
    color: var(--lc-muted);
    font-size: 12px;
  }

  ul {
    display: grid;
    gap: var(--lc-space-2);
    margin: var(--lc-space-2) 0 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
  }

  @media (max-width: 760px) {
    .validation-grid {
      grid-template-columns: 1fr;
    }

    .panel-header {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
