<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import {
    loadReviewCenter,
    retryReviewCenter,
    reviewQueue,
    reviewCenterState,
    selectedReview,
    selectedReviewId
  } from '$lib/stores/reviewCenter';
  import ReviewActivityTimeline from './ReviewActivityTimeline.svelte';
  import ReviewCommandBar from './ReviewCommandBar.svelte';
  import ReviewDecisionPanel from './ReviewDecisionPanel.svelte';
  import ReviewDiagnosticsPanel from './ReviewDiagnosticsPanel.svelte';
  import ReviewFindingsPanel from './ReviewFindingsPanel.svelte';
  import ReviewIdentityPanel from './ReviewIdentityPanel.svelte';
  import ReviewMetadataPanel from './ReviewMetadataPanel.svelte';
  import ReviewQueueSidebar from './ReviewQueueSidebar.svelte';
  import ReviewTextDiffPanel from './ReviewTextDiffPanel.svelte';
  import ReviewValidationPanel from './ReviewValidationPanel.svelte';
  import RepresentationDeltaPanel from './RepresentationDeltaPanel.svelte';

  $: selectedStatus = $selectedReview?.status ?? null;
  $: selectedQueueItem = $reviewQueue.find((item) => item.id === $selectedReviewId) ?? null;
  $: statusTone =
    selectedStatus === 'CLEAR'
      ? 'ready'
      : selectedStatus === 'BLOCKED'
        ? 'danger'
        : 'waiting';

  $: statusIcon =
    selectedStatus === 'CLEAR'
      ? 'check'
      : selectedStatus === 'BLOCKED'
        ? 'cancel'
        : 'audit';

  onMount(() => {
    void loadReviewCenter();
  });
</script>

<main id="review-workspace" class="review-workspace" aria-label={$t('review.workspace_label')}>
  <ReviewQueueSidebar />

  <article class="review-detail" aria-labelledby="review-center-heading">
    <header class="review-header">
      <div class="review-heading">
        <p class="review-eyebrow">{$t('review.eyebrow')}</p>
        <div class="title-row">
          <span class="title-icon" aria-hidden="true">
            <Icon name={statusIcon} size={22} />
          </span>
          <div>
            <h1 id="review-center-heading">{$t('review.title')}</h1>
            <p>{$t('review.subtitle')}</p>
          </div>
        </div>
      </div>
      <div class="header-status">
        {#if $selectedReview}
          <StatusBadge
            label={$t(`review.status.${$selectedReview.status}`)}
            tone={statusTone}
          />
        {/if}
        <span class="source-marker">
          {#if $selectedReview?.fixture}
            {$t('review.fixture_badge')}: {$selectedReview.fixtureLabel}
          {:else}
            {$t('review.source.local_control_plane')}
          {/if}
        </span>
      </div>
    </header>

    <div class="command-bar-wrap">
      <ReviewCommandBar />
    </div>

    <div class="review-content">
      {#if $reviewCenterState.status === 'idle'}
        <section class="review-state" aria-live="polite">
          <Icon name="audit" size={24} />
          <div>
            <h2>{$t('review.state.idle')}</h2>
            <p>{$t('review.state.idle_detail')}</p>
            <code>{$t('review.source.local_control_plane')}</code>
          </div>
        </section>
      {:else if $reviewCenterState.status === 'loading'}
        <section class="review-state" aria-live="polite" aria-busy="true">
          <Icon name="audit" size={24} />
          <div>
            <h2>{$t('review.state.loading')}</h2>
            <p>{$t('review.state.loading_detail')}</p>
            <code>{$t('review.source.local_control_plane')}</code>
          </div>
        </section>
      {:else if $reviewCenterState.status === 'empty'}
        <section class="review-state" aria-live="polite">
          <Icon name="audit" size={24} />
          <div>
            <h2>{$t('review.state.empty')}</h2>
            <p>{$t('review.state.empty_detail')}</p>
            <code>{$t('review.source.local_control_plane')}</code>
            <p class="decision-unavailable">{$t('review.decision.unavailable')}</p>
            <strong>{$t('review.decision.hard_stop_title')}</strong>
          </div>
          <button type="button" onclick={() => void loadReviewCenter()}>
            {$t('review.refresh')}
          </button>
        </section>
      {:else if $reviewCenterState.status === 'error'}
        <section class="review-state review-state-error" aria-live="assertive">
          <Icon name="cancel" size={24} />
          <div>
            <h2>{$t('review.state.error')}</h2>
            <p>{$reviewCenterState.error?.message ?? $t('review.state.error_detail')}</p>
            <code>{$reviewCenterState.error?.code ?? 'review_bridge_error'}</code>
          </div>
          {#if $reviewCenterState.retryable}
            <button type="button" onclick={() => void retryReviewCenter()}>
              {$t('review.retry')}
            </button>
          {/if}
        </section>
      {:else if $selectedReview}
        {#if !$selectedReview.fixture && $selectedReview.stale === true}
          <section class="stale-notice" role="alert">
            <Icon name="cancel" size={20} />
            <div>
              <strong>{$t('review.stale.title')}</strong>
              <span>{$t('review.stale.detail')}</span>
            </div>
          </section>
        {:else if !$selectedReview.fixture && $selectedReview.stale === null}
          <section class="stale-notice freshness-unknown" role="alert">
            <Icon name="audit" size={20} />
            <div>
              <strong>{$t('review.stale.unknown_title')}</strong>
              <span>{$t('review.stale.unknown_detail')}</span>
            </div>
          </section>
        {/if}

        {#if $selectedReview.detailProjectionTruncated || selectedQueueItem?.detailProjectionTruncated}
          <section
            class="detail-truncated-notice"
            role="note"
            aria-label={$t('review.detail_truncated.title')}
          >
            <Icon name="audit" size={20} />
            <div>
              <strong>{$t('review.detail_truncated.title')}</strong>
              <span>{$t('review.detail_truncated.detail')}</span>
            </div>
          </section>
        {/if}

        <ReviewIdentityPanel review={$selectedReview} />

        <div class="two-column">
          <ReviewValidationPanel review={$selectedReview} />
          <ReviewFindingsPanel review={$selectedReview} />
        </div>

        <ReviewMetadataPanel review={$selectedReview} />

        <div class="two-column">
          <ReviewTextDiffPanel review={$selectedReview} />
          <RepresentationDeltaPanel review={$selectedReview} />
        </div>

        <section class="human-preview" aria-labelledby="human-review-preview-heading">
          <header>
            <div>
              <p class="panel-eyebrow">{$t('review.preview.eyebrow')}</p>
              <h2 id="human-review-preview-heading">{$t('review.preview.title')}</h2>
            </div>
            {#if $selectedReview.humanReviewPreview.truncated}
              <span class="truncated-badge">{$t('review.preview.truncated')}</span>
            {/if}
          </header>
          <pre>{$selectedReview.humanReviewPreview.text}</pre>
        </section>

        <ReviewDecisionPanel review={$selectedReview} />

        <div class="two-column command-center-observability">
          <ReviewDiagnosticsPanel />
          <ReviewActivityTimeline />
        </div>

        <section class="phase-boundary" aria-label={$t('review.phase_boundary.title')}>
          <Icon name="shield" size={20} />
          <div>
            <strong>{$t('review.phase_boundary.title')}</strong>
            <span>{$t('review.phase_boundary.detail')}</span>
          </div>
        </section>
      {/if}
    </div>
  </article>
</main>

<style>
  .review-workspace {
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
    overflow: hidden;
    background: var(--lc-bg);
  }

  .review-detail {
    min-width: 0;
    min-height: 0;
    overflow: auto;
  }

  .review-header {
    position: sticky;
    top: 0;
    z-index: 10;
    min-height: 88px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-4);
    border-bottom: var(--border-thin);
    background: color-mix(in srgb, var(--lc-bg-elevated) 94%, transparent);
    backdrop-filter: blur(18px);
    padding: var(--lc-space-3) var(--lc-space-5);
  }

  .review-heading {
    min-width: 0;
  }

  .review-eyebrow,
  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  .title-row {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-3);
  }

  .title-icon {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    color: var(--lc-accent);
  }

  h1,
  h2 {
    margin: 0;
  }

  h1 {
    font-size: clamp(18px, 2vw, 24px);
  }

  .title-row p {
    margin: 4px 0 0;
    color: var(--lc-muted);
    font-size: 12px;
  }

  .header-status {
    display: grid;
    justify-items: end;
    gap: var(--lc-space-2);
  }

  .source-marker {
    max-width: 320px;
    overflow-wrap: anywhere;
    color: var(--lc-info);
    font-family: var(--lc-mono);
    font-size: 10px;
    text-align: right;
  }

  .review-state {
    min-height: 220px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: start;
    gap: var(--lc-space-4);
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-5);
    color: var(--lc-accent);
  }

  .review-state div {
    display: grid;
    gap: var(--lc-space-2);
  }

  .review-state h2,
  .review-state p {
    margin: 0;
  }

  .review-state p {
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.55;
  }

  .review-state code {
    overflow-wrap: anywhere;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .review-state button {
    min-height: 44px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    padding: 0 var(--lc-space-4);
    cursor: pointer;
  }

  .review-state button:focus-visible {
    outline: 1px solid var(--lc-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
  }

  .review-state-error {
    color: var(--lc-danger);
  }

  .review-state .decision-unavailable {
    color: var(--lc-warning);
  }

  .review-content {
    width: min(1180px, 100%);
    display: grid;
    gap: var(--lc-space-4);
    margin: 0 auto;
    padding: var(--lc-space-5);
  }

  .two-column {
    min-width: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-4);
  }

  .human-preview {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .human-preview header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  .human-preview h2 {
    font-size: 16px;
  }

  .human-preview pre {
    max-height: 280px;
    overflow: auto;
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--color-code);
    color: var(--lc-text);
    padding: var(--lc-space-3);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
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

  .phase-boundary {
    min-height: 56px;
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-info) 38%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-info) 6%, transparent);
    color: var(--lc-info);
    padding: var(--lc-space-3) var(--lc-space-4);
  }

  .detail-truncated-notice {
    min-height: 56px;
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-warning) 48%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
    padding: var(--lc-space-3) var(--lc-space-4);
  }

  .detail-truncated-notice div {
    display: grid;
    gap: 3px;
  }

  .detail-truncated-notice strong {
    font-size: 12px;
  }

  .detail-truncated-notice span {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  .phase-boundary div {
    display: grid;
    gap: 3px;
  }

  .phase-boundary strong {
    font-size: 12px;
  }

  .phase-boundary span {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  @media (max-width: 920px) {
    .review-workspace {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto minmax(0, 1fr);
    }

    .review-header {
      position: static;
      padding-inline: var(--lc-space-4);
    }

    .review-content {
      padding: var(--lc-space-4);
    }
  }

  @media (max-width: 760px) {
    .review-header {
      align-items: stretch;
      flex-direction: column;
    }

    .header-status {
      justify-items: start;
    }

    .source-marker {
      text-align: left;
    }

    .review-state {
      grid-template-columns: 1fr;
    }

    .review-state button {
      width: 100%;
    }

    .two-column {
      grid-template-columns: 1fr;
    }

    .review-content {
      padding: var(--lc-space-3);
    }
  }

  .command-bar-wrap {
    padding: var(--lc-space-4) var(--lc-space-5) 0;
  }

  .stale-notice {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-danger) 46%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-danger) 8%, transparent);
    padding: var(--lc-space-4);
    color: var(--lc-danger);
  }

  .stale-notice.freshness-unknown {
    border-color: color-mix(in srgb, var(--lc-warning) 46%, transparent);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
  }

  .stale-notice div {
    display: grid;
    gap: 4px;
  }

  .stale-notice span {
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
  }

  .command-center-observability {
    align-items: start;
  }

</style>
