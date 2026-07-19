<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import type { LineEndingProfileView, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  function profileText(profile: LineEndingProfileView | null): string {
    if (!profile) return $t('review.representation.absent');
    return `${profile.label} · CRLF ${profile.crlfCount} · LF ${profile.lfCount} · CR ${profile.crCount}`;
  }
</script>

<section class="review-panel" aria-labelledby="review-representation-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.representation.eyebrow')}</p>
      <h2 id="review-representation-heading">{$t('review.representation.title')}</h2>
    </div>
    {#if review.representationDelta?.rawTextChangedSemanticEqual}
      <span class="representation-badge">
        <Icon name="audit" size={15} />
        {$t('review.representation.only')}
      </span>
    {/if}
  </header>

  {#if review.representationDelta === null}
    <div class="no-material">
      {$t('review.representation.no_material')}
    </div>
  {:else}
    <dl class="representation-list">
      <div>
        <dt>{$t('review.representation.identity')}</dt>
        <dd><code>{review.representationDelta.identity}</code></dd>
      </div>
      <div>
        <dt>{$t('review.representation.line_endings')}</dt>
        <dd>
          <span>{profileText(review.representationDelta.beforeLineEndings)}</span>
          <span aria-hidden="true">→</span>
          <span>{profileText(review.representationDelta.afterLineEndings)}</span>
        </dd>
      </div>
      <div>
        <dt>{$t('review.representation.terminal_newline')}</dt>
        <dd>
          {review.representationDelta.terminalNewlineChanged ? $t('review.changed') : $t('review.unchanged')}
        </dd>
      </div>
      <div>
        <dt>{$t('review.representation.source_bytes_known')}</dt>
        <dd>{review.representationDelta.afterSourceBytesKnown ? $t('review.yes') : $t('review.no')}</dd>
      </div>
      <div>
        <dt>{$t('review.representation.bytes_same_text')}</dt>
        <dd>{review.representationDelta.sourceBytesChangedTextIdentical ? $t('review.yes') : $t('review.no')}</dd>
      </div>
      <div>
        <dt>{$t('review.representation.raw_semantic_equal')}</dt>
        <dd class:highlight={review.representationDelta.rawTextChangedSemanticEqual}>
          {review.representationDelta.rawTextChangedSemanticEqual ? $t('review.yes') : $t('review.no')}
        </dd>
      </div>
      <div>
        <dt>{$t('review.representation.semantic_changed')}</dt>
        <dd>{review.representationDelta.semanticContentChanged ? $t('review.yes') : $t('review.no')}</dd>
      </div>
    </dl>
  {/if}
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

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .representation-badge {
    min-height: 28px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 0 9px;
    font-size: 10px;
    font-weight: 800;
  }

  .representation-list {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .representation-list > div {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(170px, 0.35fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 11px;
  }

  dd {
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    overflow-wrap: anywhere;
    margin: 0;
    color: var(--lc-text);
    font-size: 11px;
  }

  dd.highlight {
    color: var(--lc-warning);
    font-weight: 800;
  }

  code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  .no-material {
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    color: var(--lc-muted);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  @media (max-width: 760px) {
    .representation-list > div {
      grid-template-columns: 1fr;
    }

    .panel-header {
      flex-direction: column;
    }
  }
</style>
