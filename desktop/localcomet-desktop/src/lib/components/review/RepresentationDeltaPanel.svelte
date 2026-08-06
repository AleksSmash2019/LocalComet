<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import ReviewPanel from './ReviewPanel.svelte';
  import type { LineEndingProfileView, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  function profileText(profile: LineEndingProfileView | null): string {
    if (!profile) return $t('review.representation.absent');
    return `${profile.label} · CRLF ${profile.crlfCount} · LF ${profile.lfCount} · CR ${profile.crCount}`;
  }
</script>

<ReviewPanel
  headingId="review-representation-heading"
  eyebrowKey="review.representation.eyebrow"
  titleKey="review.representation.title"
>
  <svelte:fragment slot="header-aside">
    {#if review.representationDelta?.rawTextChangedSemanticEqual}
      <span class="representation-badge">
        <Icon name="audit" size={15} />
        {$t('review.representation.only')}
      </span>
    {/if}
  </svelte:fragment>

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
</ReviewPanel>

<style>
  /* Panel frame styles live in ReviewPanel.svelte. */
</style>
