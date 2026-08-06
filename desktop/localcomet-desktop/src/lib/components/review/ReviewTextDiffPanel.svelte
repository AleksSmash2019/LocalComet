<script lang="ts">
  import { t } from '$lib/i18n';
  import ReviewPanel from './ReviewPanel.svelte';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;
</script>

<ReviewPanel
  headingId="review-diff-heading"
  eyebrowKey="review.diff.eyebrow"
  titleKey="review.diff.title"
>
  <svelte:fragment slot="header-aside">
    {#if review.textDiff.previewTruncated}
      <span class="truncated-badge">{$t('review.diff.truncated')}</span>
    {/if}
  </svelte:fragment>

  <p class="preview-contract">
    <strong>{$t('review.diff.preview_label')}</strong>
    <span>{$t('review.diff.not_full_diff')}</span>
  </p>

  {#if review.status === 'BLOCKED' || review.textDiff.preview === null}
    <div class="no-material">
      <strong>{$t('review.diff.no_material')}</strong>
      <span>{$t('review.diff.blocked_suppression')}</span>
    </div>
  {:else}
    <pre class="diff-preview" aria-label={$t('review.diff.preview_label')}>{review.textDiff.preview || $t('review.diff.empty')}</pre>
  {/if}

  <dl class="diff-meta">
    <div>
      <dt>{$t('review.diff.hash')}</dt>
      <dd><code>{review.textDiff.fullDiffHash ?? $t('review.unavailable')}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diff.bytes')}</dt>
      <dd>{review.textDiff.fullDiffUtf8Bytes ?? $t('review.unavailable')}</dd>
    </div>
    <div>
      <dt>{$t('review.diff.full_available')}</dt>
      <dd>{review.textDiff.fullDiffAvailable ? $t('review.yes') : $t('review.no')}</dd>
    </div>
    <div>
      <dt>{$t('review.diff.preview_truncated')}</dt>
      <dd>{review.textDiff.previewTruncated ? $t('review.yes') : $t('review.no')}</dd>
    </div>
  </dl>
</ReviewPanel>

<style>
  /* Panel frame styles live in ReviewPanel.svelte. */
</style>
