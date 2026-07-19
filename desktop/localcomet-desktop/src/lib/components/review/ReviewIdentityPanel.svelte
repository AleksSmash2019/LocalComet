<script module lang="ts">
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export type ReviewIdentityRow = Readonly<{
    key: string;
    labelKey: string;
    value: string | null;
  }>;

  export type ReviewClipboard = {
    writeText: (value: string) => Promise<void>;
  };

  export function getReviewIdentityRows(review: ReviewCenterItem): readonly ReviewIdentityRow[] {
    return [
      { key: 'proposal', labelKey: 'review.identity.proposal_id', value: review.proposalId },
      { key: 'review', labelKey: 'review.identity.review_identity', value: review.reviewArtifactIdentity },
      { key: 'change', labelKey: 'review.identity.change_identity', value: review.changeIdentity },
      { key: 'expected', labelKey: 'review.identity.expected_revision', value: review.expectedVaultRevision },
      { key: 'observed', labelKey: 'review.identity.observed_revision', value: review.observedVaultRevision },
      { key: 'target', labelKey: 'review.identity.target_id', value: review.targetStableId },
      { key: 'operation', labelKey: 'review.identity.operation', value: review.operation }
    ];
  }

  export function isReviewCopyActivationKey(key: string): boolean {
    return key === 'Enter' || key === ' ';
  }

  export async function writeReviewValueToClipboard(
    value: string,
    clipboard: ReviewClipboard | undefined,
    timeoutMs = 1200
  ): Promise<boolean> {
    if (!clipboard) return false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    try {
      const copyAttempt = clipboard.writeText(value).then(
        () => true,
        () => false
      );
      const timeout = new Promise<boolean>((resolve) => {
        timeoutId = setTimeout(() => resolve(false), timeoutMs);
      });
      return await Promise.race([copyAttempt, timeout]);
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    }
  }
</script>

<script lang="ts">
  import { onDestroy } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';

  export let review: ReviewCenterItem;

  type CopyFeedback = Readonly<{
    key: string;
    outcome: 'success' | 'failure';
  }>;

  let copyFeedback: CopyFeedback | null = null;
  let feedbackTimer: number | null = null;
  let feedbackReviewId = review.id;

  $: rows = getReviewIdentityRows(review);
  $: if (review.id !== feedbackReviewId) {
    feedbackReviewId = review.id;
    copyFeedback = null;
    clearFeedbackTimer();
  }

  function clearFeedbackTimer(): void {
    if (feedbackTimer === null || typeof window === 'undefined') return;
    window.clearTimeout(feedbackTimer);
    feedbackTimer = null;
  }

  async function copyValue(key: string, value: string): Promise<void> {
    const clipboard = typeof navigator === 'undefined' ? undefined : navigator.clipboard;
    const copied = await writeReviewValueToClipboard(value, clipboard);
    copyFeedback = { key, outcome: copied ? 'success' : 'failure' };
    clearFeedbackTimer();
    if (typeof window !== 'undefined') {
      feedbackTimer = window.setTimeout(() => {
        if (copyFeedback?.key === key) copyFeedback = null;
        feedbackTimer = null;
      }, 2200);
    }
  }

  function handleCopyKeydown(event: KeyboardEvent, key: string, value: string): void {
    if (!isReviewCopyActivationKey(event.key)) return;
    event.preventDefault();
    void copyValue(key, value);
  }

  onDestroy(clearFeedbackTimer);
</script>

<section class="review-panel identity-panel" aria-labelledby="review-identity-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.identity.eyebrow')}</p>
      <h2 id="review-identity-heading">{$t('review.identity.title')}</h2>
    </div>
    <span class:fixture-badge={review.fixture} class:source-badge={!review.fixture}>
      {review.fixture
        ? $t('review.fixture_badge')
        : $t('review.source.local_control_plane')}
    </span>
  </header>

  <dl class="identity-list">
    {#each rows as row}
      {@const key = row.key}
      {@const value = row.value}
      <div class="identity-row">
        <dt>{$t(row.labelKey)}</dt>
        <dd>
          <code class:value-unavailable={!value}>{value ?? $t('review.unavailable')}</code>
          {#if value}
            <button
              type="button"
              class="copy-button"
              aria-label={`${$t('review.copy')} ${$t(row.labelKey)}`}
              title={$t('review.copy')}
              onclick={() => void copyValue(key, value)}
              onkeydown={(event) => handleCopyKeydown(event, key, value)}
            >
              <Icon
                name={copyFeedback?.key === key
                  ? copyFeedback.outcome === 'success'
                    ? 'check'
                    : 'cancel'
                  : 'link'}
                size={16}
              />
              <span>
                {copyFeedback?.key === key
                  ? copyFeedback.outcome === 'success'
                    ? $t('review.copied')
                    : $t('review.copy_failed')
                  : $t('review.copy')}
              </span>
            </button>
          {/if}
        </dd>
      </div>
    {/each}
  </dl>
  <p
    class:copy-error={copyFeedback?.outcome === 'failure'}
    class="copy-announcement"
    aria-live="polite"
    aria-atomic="true"
  >
    {copyFeedback
      ? copyFeedback.outcome === 'success'
        ? $t('review.copy_success')
        : $t('review.copy_failure')
      : ''}
  </p>
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

  .fixture-badge {
    border: 1px solid color-mix(in srgb, var(--lc-info) 45%, transparent);
    border-radius: 999px;
    color: var(--lc-info);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .source-badge {
    border: 1px solid color-mix(in srgb, var(--lc-accent) 45%, transparent);
    border-radius: 999px;
    color: var(--lc-accent);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .identity-list {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .identity-row {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(140px, 0.35fr) minmax(0, 1fr);
    align-items: start;
    gap: var(--lc-space-3);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 720;
  }

  dd {
    min-width: 0;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-2);
    margin: 0;
  }

  code {
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .value-unavailable {
    color: var(--lc-faint);
  }

  .copy-button {
    flex: 0 0 auto;
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: 0 var(--lc-space-3);
    cursor: pointer;
  }

  .copy-button:hover {
    border-color: var(--lc-line-strong);
    color: var(--lc-accent);
  }

  .copy-button:focus-visible {
    outline: 1px solid var(--lc-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
  }

  .copy-announcement {
    min-height: 1em;
    margin: var(--lc-space-2) 0 0;
    color: var(--lc-accent);
    font-size: 11px;
  }

  .copy-announcement.copy-error {
    color: var(--lc-danger);
  }

  @media (max-width: 760px) {
    .identity-row {
      grid-template-columns: 1fr;
    }

    dd {
      flex-direction: column;
    }

    .copy-button {
      width: 100%;
      justify-content: center;
    }
  }
</style>
