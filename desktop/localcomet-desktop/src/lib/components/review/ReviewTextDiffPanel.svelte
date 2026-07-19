<script lang="ts">
  import { t } from '$lib/i18n';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;
</script>

<section class="review-panel" aria-labelledby="review-diff-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.diff.eyebrow')}</p>
      <h2 id="review-diff-heading">{$t('review.diff.title')}</h2>
    </div>
    {#if review.textDiff.previewTruncated}
      <span class="truncated-badge">{$t('review.diff.truncated')}</span>
    {/if}
  </header>

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
</section>

<style>
  .review-panel {
    min-width: 0;
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
    margin-bottom: var(--lc-space-3);
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

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .truncated-badge {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .preview-contract {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    margin: 0 0 var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
  }

  .preview-contract strong {
    color: var(--lc-text);
  }

  .diff-preview {
    min-height: 96px;
    max-height: 420px;
    overflow: auto;
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--color-code);
    color: var(--lc-text);
    padding: var(--lc-space-3);
    white-space: pre;
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .no-material {
    display: grid;
    gap: 6px;
    border: 1px solid color-mix(in srgb, var(--lc-danger) 38%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-danger) 7%, transparent);
    color: var(--lc-muted);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  .no-material strong {
    color: var(--lc-danger);
  }

  .diff-meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-3);
    margin: var(--lc-space-4) 0 0;
  }

  .diff-meta > div {
    min-width: 0;
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    margin-bottom: 4px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  dd {
    min-width: 0;
    overflow-wrap: anywhere;
    margin: 0;
    color: var(--lc-text);
    font-size: 11px;
  }

  code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  @media (max-width: 760px) {
    .diff-meta {
      grid-template-columns: 1fr;
    }

    .diff-preview {
      max-height: 320px;
    }
  }
</style>
