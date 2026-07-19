<script lang="ts">
  import { t } from '$lib/i18n';
  import { reviewActivity } from '$lib/stores/reviewCenter';
</script>

<section class="activity review-panel" aria-labelledby="review-activity-title">
  <header>
    <div>
      <p>{$t('review.activity.eyebrow')}</p>
      <h2 id="review-activity-title">{$t('review.activity.title')}</h2>
    </div>
    <span>{$reviewActivity.length}/128</span>
  </header>

  {#if $reviewActivity.length === 0}
    <p class="empty">{$t('review.activity.empty')}</p>
  {:else}
    <ol aria-live="polite">
      {#each [...$reviewActivity].reverse() as event (event.id)}
        <li>
          <span class="sequence">{event.sequence}</span>
          <div>
            <strong>{$t(event.messageKey)}</strong>
            {#if event.reviewArtifactIdentity}
              <code>{event.reviewArtifactIdentity}</code>
            {/if}
            {#if event.errorCode}
              <span class="error-code">{event.errorCode}</span>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  <p class="boundary">{$t('review.activity.boundary')}</p>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  header p {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  header span {
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  h2,
  .empty {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  .empty,
  .boundary {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  ol {
    display: grid;
    gap: var(--lc-space-2);
    max-height: 320px;
    overflow: auto;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    min-width: 0;
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr);
    gap: var(--lc-space-2);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  .sequence {
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  li div {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  strong {
    font-size: 12px;
  }

  code,
  .error-code {
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  .error-code {
    color: var(--lc-danger);
  }

  .boundary {
    margin: var(--lc-space-3) 0 0;
  }
</style>
