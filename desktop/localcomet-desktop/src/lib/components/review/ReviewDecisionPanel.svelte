<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import DecisionConfirmationDialog from './DecisionConfirmationDialog.svelte';
  import { t } from '$lib/i18n';
  import {
    closeDecisionDialog,
    confirmDecision,
    decisionDialog,
    decisionResult,
    openDecisionDialog,
    setDecisionActorDisplayName,
    setDecisionActorIdentifier,
    setDecisionComment
  } from '$lib/stores/reviewCenter';
  import type { DecisionIntent, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  let triggerElement: HTMLElement | null = null;

  $: realReview = review.fixture === false;
  $: staleOrUnknown = review.fixture === false && review.stale !== false;
  $: approveDisabled =
    $decisionDialog.submitting || review.status === 'BLOCKED' || staleOrUnknown;
  $: otherDisabled = $decisionDialog.submitting || staleOrUnknown;
  $: resultForReview =
    $decisionResult &&
    ($decisionResult.fixture
      ? $decisionResult.reviewArtifactIdentity === review.reviewArtifactIdentity
      : $decisionResult.decision.review_artifact_identity === review.reviewArtifactIdentity)
      ? $decisionResult
      : null;

  function requestIntent(intent: DecisionIntent, event: MouseEvent): void {
    triggerElement = event.currentTarget as HTMLElement;
    openDecisionDialog(review, intent);
  }

  async function confirm(): Promise<void> {
    await confirmDecision(review);
  }
</script>

<section class="review-panel decision-panel" aria-labelledby="review-decision-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.decision.eyebrow')}</p>
      <h2 id="review-decision-heading">{$t('review.decision.title')}</h2>
    </div>
    <span class:fixture-badge={!realReview} class:real-badge={realReview}>
      {realReview
        ? $t('review.decision.real_e9c')
        : $t('review.decision.fixture_only')}
    </span>
  </header>

  <p class="decision-boundary">
    {realReview
      ? $t('review.decision.real_boundary')
      : $t('review.decision.boundary')}
  </p>

  {#if review.fixture === false && review.stale === true}
    <p class="stale-note" role="alert">{$t('review.decision.stale')}</p>
  {:else if review.fixture === false && review.stale === null}
    <p class="stale-note" role="alert">{$t('review.decision.freshness_unknown')}</p>
  {/if}

  <div class="decision-actions" role="group" aria-label={$t('review.decision.actions')}>
    <button
      type="button"
      class="approve-button"
      disabled={approveDisabled}
      aria-disabled={approveDisabled}
      title={review.status === 'BLOCKED'
        ? $t('review.decision.blocked_approval')
        : staleOrUnknown
          ? $t('review.decision.stale_or_unknown')
          : $t('review.decision.approve')}
      onclick={(event) => requestIntent('APPROVE', event)}
    >
      <Icon name="check" size={18} />
      {$t('review.decision.approve')}
    </button>
    <button
      type="button"
      class="reject-button"
      disabled={otherDisabled}
      aria-disabled={otherDisabled}
      title={staleOrUnknown
        ? $t('review.decision.stale_or_unknown')
        : $t('review.decision.reject')}
      onclick={(event) => requestIntent('REJECT', event)}
    >
      <Icon name="cancel" size={18} />
      {$t('review.decision.reject')}
    </button>
    <button
      type="button"
      class="request-button"
      disabled={otherDisabled}
      aria-disabled={otherDisabled}
      title={staleOrUnknown
        ? $t('review.decision.stale_or_unknown')
        : $t('review.decision.request_changes')}
      onclick={(event) => requestIntent('REQUEST_CHANGES', event)}
    >
      <Icon name="audit" size={18} />
      {$t('review.decision.request_changes')}
    </button>
  </div>

  {#if review.status === 'BLOCKED'}
    <p class="blocked-note">{$t('review.decision.blocked_approval')}</p>
  {/if}

  <div class="decision-result" aria-live="polite" aria-atomic="true">
    {#if resultForReview?.fixture}
      <strong>{$t('review.decision.fixture_result')}</strong>
      <span>{$t(resultForReview.messageKey)}</span>
      <code>{resultForReview.intent}</code>
    {:else if resultForReview && !resultForReview.fixture}
      <strong>{$t('review.decision.real_result')}</strong>
      <span>{$t(resultForReview.messageKey)}</span>
      <dl>
        <div>
          <dt>{$t('review.decision.decision_identity')}</dt>
          <dd><code>{resultForReview.decision.decision_identity}</code></dd>
        </div>
        <div>
          <dt>{$t('review.decision.intent')}</dt>
          <dd><code>{resultForReview.decision.decision}</code></dd>
        </div>
        <div>
          <dt>{$t('review.decision.vault_modified')}</dt>
          <dd>{$t('review.no')}</dd>
        </div>
      </dl>
    {/if}
  </div>

  <div class="hard-stop">
    <Icon name="shield" size={17} />
    <div>
      <strong>{$t('review.decision.hard_stop_title')}</strong>
      <span>
        {realReview
          ? $t('review.decision.real_hard_stop_detail')
          : $t('review.decision.hard_stop_detail')}
      </span>
    </div>
  </div>
</section>

{#if $decisionDialog.open && $decisionDialog.intent}
  <DecisionConfirmationDialog
    {review}
    intent={$decisionDialog.intent}
    comment={$decisionDialog.comment}
    actorIdentifier={$decisionDialog.actorIdentifier}
    actorDisplayName={$decisionDialog.actorDisplayName}
    submitting={$decisionDialog.submitting}
    errorKey={$decisionDialog.errorKey}
    {triggerElement}
    onClose={closeDecisionDialog}
    onComment={setDecisionComment}
    onActorIdentifier={setDecisionActorIdentifier}
    onActorDisplayName={setDecisionActorDisplayName}
    onConfirm={confirm}
  />
{/if}

<style>
  .review-panel {
    border: 1px solid var(--lc-line-strong);
    border-radius: var(--lc-radius-lg);
    background: linear-gradient(180deg, var(--lc-accent-dim), var(--lc-panel));
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

  .fixture-badge,
  .real-badge {
    border: 1px solid color-mix(in srgb, var(--lc-info) 45%, transparent);
    border-radius: 999px;
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .fixture-badge {
    color: var(--lc-info);
  }

  .real-badge {
    color: var(--lc-accent);
  }

  .decision-boundary {
    margin: 0 0 var(--lc-space-4);
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.55;
  }

  .decision-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--lc-space-3);
  }

  .decision-actions button {
    min-height: 48px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    border-radius: var(--lc-radius-md);
    padding: 0 var(--lc-space-3);
    font-size: 12px;
    font-weight: 820;
    cursor: pointer;
  }

  .decision-actions button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .decision-actions button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  .approve-button {
    border: 1px solid var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .reject-button {
    border: 1px solid color-mix(in srgb, var(--lc-danger) 42%, transparent);
    background: color-mix(in srgb, var(--lc-danger) 8%, transparent);
    color: var(--lc-danger);
  }

  .request-button {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
  }

  .blocked-note,
  .stale-note {
    margin: var(--lc-space-3) 0 0;
    color: var(--lc-danger);
    font-size: 12px;
  }

  .stale-note {
    margin: 0 0 var(--lc-space-3);
  }

  .decision-result {
    min-height: 22px;
    display: grid;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-4);
  }

  .decision-result strong {
    color: var(--lc-accent);
  }

  .decision-result span,
  .decision-result code,
  .decision-result dt,
  .decision-result dd {
    overflow-wrap: anywhere;
    font-size: 11px;
  }

  .decision-result code {
    font-family: var(--lc-mono);
  }

  .decision-result dl {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .decision-result dl > div {
    display: grid;
    grid-template-columns: minmax(120px, 0.35fr) minmax(0, 1fr);
    gap: var(--lc-space-2);
  }

  .decision-result dd {
    margin: 0;
  }

  .hard-stop {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    margin-top: var(--lc-space-4);
    padding: var(--lc-space-3);
    color: var(--lc-warning);
  }

  .hard-stop div {
    display: grid;
    gap: 4px;
  }

  .hard-stop span {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  @media (max-width: 760px) {
    .decision-actions {
      grid-template-columns: 1fr;
    }

    .decision-result dl > div {
      grid-template-columns: 1fr;
    }
  }
</style>
