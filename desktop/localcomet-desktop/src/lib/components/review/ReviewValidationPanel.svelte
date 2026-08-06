<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import ReviewPanel from './ReviewPanel.svelte';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  $: validationTone =
    review.validation.outcome === 'VALID'
      ? 'ready'
      : review.validation.outcome === 'STALE'
        ? 'waiting'
        : 'danger';
</script>

<ReviewPanel
  headingId="review-validation-heading"
  eyebrowKey="review.validation.eyebrow"
  titleKey="review.validation.title"
>
  <StatusBadge
    slot="header-aside"
    label={$t(`review.validation.outcome.${review.validation.outcome}`)}
    tone={validationTone}
  />

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
</ReviewPanel>

<style>
  /* Panel frame styles live in ReviewPanel.svelte. */
</style>
