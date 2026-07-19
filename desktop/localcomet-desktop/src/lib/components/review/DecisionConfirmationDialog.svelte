<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { t } from '$lib/i18n';
  import { cycleDialogFocusIndex } from '$lib/stores/reviewCenter';
  import type { DecisionIntent, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;
  export let intent: DecisionIntent;
  export let comment: string;
  export let actorIdentifier = '';
  export let actorDisplayName = '';
  export let submitting = false;
  export let errorKey: string | null = null;
  export let triggerElement: HTMLElement | null = null;
  export let onClose: () => void = () => {};
  export let onComment: (value: string) => void = () => {};
  export let onActorIdentifier: (value: string) => void = () => {};
  export let onActorDisplayName: (value: string) => void = () => {};
  export let onConfirm: () => void | Promise<void> = () => {};

  let dialogElement: HTMLDivElement;
  let previousFocus: HTMLElement | null = null;

  const focusableSelector = [
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[href]',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  onMount(() => {
    previousFocus =
      triggerElement ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    void tick().then(() => {
      dialogElement?.querySelectorAll<HTMLElement>(focusableSelector)?.[0]?.focus();
    });
  });

  onDestroy(() => {
    (triggerElement ?? previousFocus)?.focus();
  });

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      if (submitting) return;
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;

    const focusable = Array.from(
      dialogElement.querySelectorAll<HTMLElement>(focusableSelector)
    );
    if (focusable.length === 0) {
      event.preventDefault();
      dialogElement.focus();
      return;
    }
    const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const nextIndex = cycleDialogFocusIndex(currentIndex, focusable.length, event.shiftKey);
    event.preventDefault();
    focusable[nextIndex]?.focus();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (!submitting && event.target === event.currentTarget) onClose();
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!submitting) void onConfirm();
  }

  $: intentKey = `review.decision.${intent.toLowerCase()}`;
  $: exactChange = review.changeIdentity ?? $t('review.none');
</script>

<div
  class="dialog-backdrop"
  role="presentation"
  onclick={handleBackdropClick}
  onkeydown={handleKeydown}
>
  <div
    bind:this={dialogElement}
    class="decision-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="review-decision-dialog-title"
    aria-describedby="review-decision-dialog-description"
    aria-busy={submitting}
    tabindex="-1"
  >
    <form onsubmit={submit}>
      <header>
        <p class="dialog-eyebrow">
          {review.fixture
            ? $t('review.decision.fixture_only')
            : $t('review.decision.real_e9c')}
        </p>
        <h2 id="review-decision-dialog-title">{$t('review.decision.dialog_title')}</h2>
        <p id="review-decision-dialog-description">
          {review.fixture
            ? $t('review.decision.dialog_description_fixture')
            : $t('review.decision.dialog_description_real')}
        </p>
      </header>

      <dl class="binding-grid">
        <div>
          <dt>{$t('review.identity.proposal_id')}</dt>
          <dd><code>{review.proposalId}</code></dd>
        </div>
        <div>
          <dt>{$t('review.identity.review_identity')}</dt>
          <dd><code>{review.reviewArtifactIdentity}</code></dd>
        </div>
        <div>
          <dt>{$t('review.identity.change_identity')}</dt>
          <dd><code>{exactChange}</code></dd>
        </div>
        <div>
          <dt>{$t('review.identity.observed_revision')}</dt>
          <dd><code>{review.observedVaultRevision}</code></dd>
        </div>
        <div>
          <dt>{$t('review.decision.intent')}</dt>
          <dd><strong>{$t(intentKey)}</strong></dd>
        </div>
      </dl>

      {#if !review.fixture}
        <div class="actor-grid">
          <label for="review-actor-identifier">
            {$t('review.decision.actor_identifier')}
            <input
              id="review-actor-identifier"
              value={actorIdentifier}
              maxlength="256"
              autocomplete="off"
              disabled={submitting}
              oninput={(event) =>
                onActorIdentifier((event.currentTarget as HTMLInputElement).value)}
            />
          </label>
          <label for="review-actor-display-name">
            {$t('review.decision.actor_display_name')}
            <input
              id="review-actor-display-name"
              value={actorDisplayName}
              maxlength="256"
              autocomplete="off"
              disabled={submitting}
              oninput={(event) =>
                onActorDisplayName((event.currentTarget as HTMLInputElement).value)}
            />
          </label>
        </div>
        <p class="actor-note">{$t('review.decision.actor_evidence_only')}</p>
      {/if}

      <label for="review-decision-comment">
        {$t('review.decision.comment')}
        {#if intent === 'REQUEST_CHANGES'}
          <span class="required">{$t('review.decision.required')}</span>
        {/if}
      </label>
      <textarea
        id="review-decision-comment"
        value={comment}
        maxlength="2000"
        rows="5"
        disabled={submitting}
        aria-invalid={Boolean(errorKey)}
        aria-describedby={errorKey ? 'review-decision-error' : undefined}
        placeholder={$t('review.decision.comment_placeholder')}
        oninput={(event) => onComment((event.currentTarget as HTMLTextAreaElement).value)}
      ></textarea>

      {#if errorKey}
        <p id="review-decision-error" class="dialog-error" role="alert">
          {$t(errorKey)}
        </p>
      {/if}

      <p class="hard-stop-note">
        <strong>{$t('review.decision.hard_stop_title')}</strong>
        {review.fixture
          ? $t('review.decision.hard_stop_detail')
          : $t('review.decision.real_hard_stop_detail')}
      </p>

      <footer>
        <button type="button" class="secondary-button" disabled={submitting} onclick={onClose}>
          {$t('review.decision.cancel')}
        </button>
        <button type="submit" class="primary-button" disabled={submitting}>
          {submitting ? $t('review.decision.submitting') : $t('review.decision.confirm')}
        </button>
      </footer>
    </form>
  </div>
</div>

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    z-index: 90;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.66);
    padding: var(--lc-space-4);
  }

  .decision-dialog {
    width: min(680px, 100%);
    max-height: min(800px, calc(100vh - 32px));
    overflow: auto;
    border: 1px solid var(--lc-line-strong);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
  }

  form {
    display: grid;
    gap: var(--lc-space-4);
    padding: var(--lc-space-5);
  }

  header {
    display: grid;
    gap: var(--lc-space-2);
  }

  .dialog-eyebrow {
    margin: 0;
    color: var(--lc-info);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 820;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 20px;
  }

  header p:last-child,
  .actor-note {
    margin: 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
  }

  .binding-grid {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .binding-grid > div {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(150px, 0.32fr) minmax(0, 1fr);
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
    margin: 0;
    overflow-wrap: anywhere;
    font-size: 11px;
  }

  code {
    font-family: var(--lc-mono);
  }

  .actor-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-3);
  }

  label {
    display: grid;
    gap: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  input,
  textarea {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel);
    color: var(--lc-text);
    font: inherit;
    padding: var(--lc-space-3);
  }

  input {
    min-height: 44px;
  }

  textarea {
    resize: vertical;
  }

  input:focus-visible,
  textarea:focus-visible,
  button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .required,
  .dialog-error {
    color: var(--lc-danger);
  }

  .dialog-error {
    margin: 0;
    font-size: 12px;
  }

  .hard-stop-note {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    margin: 0;
    padding: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  .hard-stop-note strong {
    display: block;
    margin-bottom: 4px;
    color: var(--lc-warning);
  }

  footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--lc-space-3);
  }

  button {
    min-height: 44px;
    border-radius: var(--lc-radius-md);
    padding: 0 var(--lc-space-4);
    font-weight: 800;
    cursor: pointer;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.56;
  }

  .secondary-button {
    border: var(--border-thin);
    background: var(--lc-panel);
    color: var(--lc-text);
  }

  .primary-button {
    border: 1px solid var(--lc-line-strong);
    background: var(--lc-accent);
    color: var(--lc-bg);
  }

  @media (max-width: 640px) {
    form {
      padding: var(--lc-space-4);
    }

    .binding-grid > div,
    .actor-grid {
      grid-template-columns: 1fr;
    }

    footer {
      display: grid;
      grid-template-columns: 1fr;
    }
  }
</style>
