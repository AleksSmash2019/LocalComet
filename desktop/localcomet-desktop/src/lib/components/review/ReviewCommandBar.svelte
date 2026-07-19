<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import {
    clearReviewFilters,
    filteredReviewQueue,
    refreshReviewCenter,
    reviewCenterState,
    reviewFilters,
    setReviewQuery,
    setReviewSort,
    toggleReviewOperation,
    toggleReviewStatus
  } from '$lib/stores/reviewCenter';
  import type { ReviewOperation, ReviewStatus } from '$lib/types/knowledgeReview';

  const statuses: readonly ReviewStatus[] = ['CLEAR', 'REVIEW_REQUIRED', 'BLOCKED'];
  const operations: readonly ReviewOperation[] = [
    'CREATE_NEW',
    'UPDATE_EXISTING',
    'DELETE',
    'MOVE',
    'RENAME',
    'SUPERSEDE'
  ];

  $: filtersActive =
    $reviewFilters.query.length > 0 ||
    $reviewFilters.statuses.length > 0 ||
    $reviewFilters.operations.length > 0;
</script>

<section class="command-bar" aria-label={$t('review.command_bar.label')}>
  <div class="search-field">
    <label for="review-search">{$t('review.command_bar.search')}</label>
    <input
      id="review-search"
      type="search"
      maxlength="200"
      value={$reviewFilters.query}
      placeholder={$t('review.command_bar.search_placeholder')}
      oninput={(event) => setReviewQuery((event.currentTarget as HTMLInputElement).value)}
    />
  </div>

  <fieldset>
    <legend>{$t('review.command_bar.status_filter')}</legend>
    <div class="filter-row">
      {#each statuses as status}
        <button
          type="button"
          class:active={$reviewFilters.statuses.includes(status)}
          aria-pressed={$reviewFilters.statuses.includes(status)}
          onclick={() => toggleReviewStatus(status)}
        >
          {$t(`review.status.${status}`)}
        </button>
      {/each}
    </div>
  </fieldset>

  <fieldset class="operation-filter">
    <legend>{$t('review.command_bar.operation_filter')}</legend>
    <div class="filter-row">
      {#each operations as operation}
        <button
          type="button"
          class:active={$reviewFilters.operations.includes(operation)}
          aria-pressed={$reviewFilters.operations.includes(operation)}
          onclick={() => toggleReviewOperation(operation)}
        >
          {operation}
        </button>
      {/each}
    </div>
  </fieldset>

  <div class="command-actions">
    <label for="review-sort">{$t('review.command_bar.sort')}</label>
    <select
      id="review-sort"
      value={$reviewFilters.sort}
      onchange={(event) =>
        setReviewSort(
          (event.currentTarget as HTMLSelectElement).value as
            | 'IDENTITY_ASC'
            | 'STATUS_THEN_IDENTITY'
        )}
    >
      <option value="STATUS_THEN_IDENTITY">{$t('review.command_bar.sort_status')}</option>
      <option value="IDENTITY_ASC">{$t('review.command_bar.sort_identity')}</option>
    </select>

    <span class="filtered-count" aria-live="polite">
      {$filteredReviewQueue.length} {$t('review.command_bar.visible')}
    </span>

    <button type="button" disabled={!filtersActive} onclick={clearReviewFilters}>
      {$t('review.command_bar.clear')}
    </button>
    <button
      type="button"
      class="refresh-button"
      disabled={$reviewCenterState.status === 'loading'}
      onclick={() => void refreshReviewCenter()}
    >
      <Icon name="refresh" size={17} />
      {$t('review.command_bar.revalidate')}
    </button>
  </div>
</section>

<style>
  .command-bar {
    display: grid;
    grid-template-columns: minmax(220px, 1.25fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .search-field,
  .command-actions {
    min-width: 0;
    display: flex;
    align-items: end;
    gap: var(--lc-space-2);
    flex-wrap: wrap;
  }

  .search-field {
    display: grid;
    align-content: start;
  }

  label,
  legend {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
  }

  input,
  select,
  button {
    min-height: 44px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
  }

  input,
  select {
    min-width: 0;
    padding: 0 var(--lc-space-3);
  }

  input {
    width: 100%;
  }

  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    padding: 0 var(--lc-space-3);
    cursor: pointer;
  }

  button.active {
    border-color: var(--lc-accent);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.52;
  }

  input:focus-visible,
  select:focus-visible,
  button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  fieldset {
    min-width: 0;
    margin: 0;
    border: 0;
    padding: 0;
  }

  .operation-filter {
    grid-column: 1 / -1;
  }

  .filter-row {
    display: flex;
    gap: var(--lc-space-2);
    flex-wrap: wrap;
    margin-top: var(--lc-space-2);
  }

  .filter-row button {
    min-height: 44px;
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  .command-actions {
    grid-column: 1 / -1;
  }

  .command-actions label {
    align-self: center;
  }

  .filtered-count {
    align-self: center;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .refresh-button {
    margin-left: auto;
    border-color: var(--lc-line-strong);
    color: var(--lc-accent);
  }

  @media (max-width: 760px) {
    .command-bar {
      grid-template-columns: 1fr;
    }

    .operation-filter,
    .command-actions {
      grid-column: 1;
    }

    .refresh-button {
      margin-left: 0;
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    * {
      scroll-behavior: auto !important;
      transition: none !important;
    }
  }
</style>
