<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import {
    filteredReviewQueue,
    moveReviewSelection,
    reviewCenterState,
    reviewFilters,
    reviewQueue,
    selectReview,
    selectReviewBoundary,
    selectedReviewId
  } from '$lib/stores/reviewCenter';
  import type { ReviewStatus } from '$lib/types/knowledgeReview';

  function statusIcon(status: ReviewStatus): string {
    if (status === 'CLEAR') return 'check';
    if (status === 'BLOCKED') return 'cancel';
    return 'audit';
  }

  function handleQueueKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveReviewSelection(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveReviewSelection(-1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectReviewBoundary('first');
    } else if (event.key === 'End') {
      event.preventDefault();
      selectReviewBoundary('last');
    } else {
      return;
    }

    requestAnimationFrame(() => {
      document
        .querySelector<HTMLButtonElement>('.review-queue-button[aria-current="true"]')
        ?.focus();
    });
  }

  $: filteredEmpty = $reviewQueue.length > 0 && $filteredReviewQueue.length === 0;
</script>

<div class="review-queue-mobile">
  <label for="review-queue-select">{$t('review.queue_mobile_label')}</label>
  <select
    id="review-queue-select"
    value={$selectedReviewId ?? ''}
    disabled={$filteredReviewQueue.length === 0}
    onchange={(event) => selectReview((event.currentTarget as HTMLSelectElement).value)}
  >
    {#if $filteredReviewQueue.length === 0}
      <option value="">
        {filteredEmpty ? $t('review.queue_filtered_empty') : $t('review.state.empty')}
      </option>
    {/if}
    {#each $filteredReviewQueue as review}
      <option value={review.id}>
        {$t(`review.status.${review.status}`)} — {review.targetStableId}
        {#if review.stale === true}— {$t('review.stale.badge')}{/if}
        {#if review.detailProjectionTruncated}— {$t('review.detail_truncated.badge')}{/if}
      </option>
    {/each}
  </select>
</div>

<nav class="review-queue" aria-label={$t('review.queue_label')}>
  <header class="queue-header">
    <div>
      <p class="eyebrow">{$t('review.queue_eyebrow')}</p>
      <h2>{$t('review.queue_title')}</h2>
    </div>
    <span class="queue-count" aria-label={$t('review.queue_visible_count')}>
      {$filteredReviewQueue.length}/{$reviewCenterState.totalCount}
    </span>
  </header>

  <p class="queue-help">{$t('review.queue_help')}</p>
  {#if $reviewCenterState.truncated}
    <p class="queue-truncated">
      {$t('review.queue_truncated')}
      {#if $reviewCenterState.nextOffset !== null}
        <code>{$reviewCenterState.nextOffset}</code>
      {/if}
    </p>
  {/if}

  {#if filteredEmpty}
    <p class="filtered-empty">
      {$t('review.queue_filtered_empty')}
      <span class="visually-hidden">{$reviewFilters.query}</span>
    </p>
  {/if}

  <div class="queue-list" role="listbox" aria-label={$t('review.queue_label')}>
    {#each $filteredReviewQueue as review (review.id)}
      <button
        type="button"
        class:active={$selectedReviewId === review.id}
        class="review-queue-button status-{review.status.toLowerCase()}"
        role="option"
        aria-selected={$selectedReviewId === review.id}
        aria-current={$selectedReviewId === review.id ? 'true' : undefined}
        onclick={() => selectReview(review.id)}
        onkeydown={handleQueueKey}
      >
        <span class="queue-status-icon" aria-hidden="true">
          <Icon name={statusIcon(review.status)} size={17} />
        </span>
        <span class="queue-copy">
          <span class="queue-status">{$t(`review.status.${review.status}`)}</span>
          <span class="queue-target">{review.targetStableId}</span>
          <span class="queue-operation">{review.operation}</span>
          {#if review.stale === true}
            <span class="stale-badge">{$t('review.stale.badge')}</span>
          {:else if review.stale === null}
            <span class="stale-badge">{$t('review.stale.unknown')}</span>
          {/if}
          {#if review.detailProjectionTruncated}
            <span class="detail-truncated-badge">{$t('review.detail_truncated.badge')}</span>
          {/if}
        </span>
        <span
          class:fixture-dot={review.fixture}
          class:source-dot={!review.fixture}
          title={review.fixture
            ? $t('review.fixture_badge')
            : $t('review.source.local_control_plane')}
          aria-hidden="true"
        ></span>
      </button>
    {/each}
  </div>
</nav>

<style>
  .review-queue {
    min-width: 0;
    min-height: 0;
    overflow: auto;
    border-right: var(--border-thin);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .queue-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  .eyebrow {
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

  .queue-count {
    display: grid;
    place-items: center;
    min-width: 28px;
    height: 28px;
    border: var(--border-thin);
    border-radius: 999px;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 12px;
  }

  .queue-help {
    margin: var(--lc-space-3) 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.45;
  }

  .queue-truncated {
    margin: calc(var(--lc-space-2) * -1) 0 var(--lc-space-3);
    color: var(--lc-warning);
    font-size: 11px;
  }

  .queue-truncated code {
    font-family: var(--lc-mono);
  }

  .queue-list {
    display: grid;
    gap: var(--lc-space-2);
  }

  .review-queue-button {
    position: relative;
    min-height: 76px;
    width: 100%;
    display: grid;
    grid-template-columns: 24px minmax(0, 1fr) 8px;
    align-items: start;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    padding: var(--lc-space-3);
    text-align: left;
    cursor: pointer;
  }

  .review-queue-button:hover,
  .review-queue-button.active {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
  }

  .review-queue-button:focus-visible,
  .review-queue-mobile select:focus-visible {
    outline: 1px solid var(--lc-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
  }

  .queue-status-icon {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
  }

  .status-clear .queue-status-icon {
    color: var(--lc-accent);
  }

  .status-review_required .queue-status-icon {
    color: var(--lc-warning);
  }

  .status-blocked .queue-status-icon {
    color: var(--lc-danger);
  }

  .queue-copy {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  .queue-status {
    color: var(--lc-text);
    font-size: 11px;
    font-weight: 820;
    letter-spacing: 0.05em;
  }

  .queue-target,
  .queue-operation {
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .detail-truncated-badge {
    width: fit-content;
    border: 1px solid color-mix(in srgb, var(--lc-warning) 48%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 2px 7px;
    font-family: var(--lc-mono);
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.06em;
  }

  .fixture-dot {
    align-self: center;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--lc-info);
  }

  .source-dot {
    align-self: center;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--lc-accent);
  }

  .review-queue-mobile {
    display: none;
  }

  @media (max-width: 920px) {
    .review-queue {
      display: none;
    }

    .review-queue-mobile {
      display: grid;
      gap: var(--lc-space-2);
      border-bottom: var(--border-thin);
      background: var(--lc-panel);
      padding: var(--lc-space-3);
    }

    .review-queue-mobile label {
      color: var(--lc-muted);
      font-size: 12px;
      font-weight: 720;
    }

    .review-queue-mobile select {
      min-height: 44px;
      width: 100%;
      border: var(--border-thin);
      border-radius: var(--lc-radius-sm);
      background: var(--lc-panel-solid);
      color: var(--lc-text);
      padding: 0 var(--lc-space-3);
    }
  }

  .stale-badge {
    color: var(--lc-warning);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .filtered-empty {
    margin: var(--lc-space-3) 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
  }
</style>
