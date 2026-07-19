<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import { sortReviewFindings } from '$lib/types/knowledgeReview';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  $: findings = sortReviewFindings(review.findings);
</script>

<section class="review-panel" aria-labelledby="review-findings-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.findings.eyebrow')}</p>
      <h2 id="review-findings-heading">{$t('review.findings.title')}</h2>
    </div>
    <span class="finding-count">{findings.length}</span>
  </header>

  {#if findings.length === 0}
    <div class="empty-findings">
      <Icon name="check" size={18} />
      <span>{$t('review.findings.none')}</span>
    </div>
  {:else}
    <ol class="finding-list">
      {#each findings as finding}
        <li class:blocking={finding.severity === 'BLOCKING'}>
          <header>
            <span class="finding-icon" aria-hidden="true">
              <Icon name={finding.severity === 'BLOCKING' ? 'cancel' : 'audit'} size={17} />
            </span>
            <div>
              <code>{finding.code}</code>
              <span class="severity">
                {$t(`review.severity.${finding.severity}`)}
              </span>
            </div>
          </header>
          <p>{finding.message}</p>
          {#if finding.details.length > 0}
            <dl>
              {#each finding.details as detail}
                <div>
                  <dt>{detail[0]}</dt>
                  <dd><code>{detail[1]}</code></dd>
                </div>
              {/each}
            </dl>
          {/if}
        </li>
      {/each}
    </ol>
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

  .finding-count {
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

  .empty-findings {
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    color: var(--lc-accent);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  .finding-list {
    display: grid;
    gap: var(--lc-space-3);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .finding-list > li {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 34%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 6%, transparent);
    padding: var(--lc-space-3);
  }

  .finding-list > li.blocking {
    border-color: color-mix(in srgb, var(--lc-danger) 40%, transparent);
    background: color-mix(in srgb, var(--lc-danger) 7%, transparent);
  }

  li > header {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-2);
  }

  .finding-icon {
    color: var(--lc-warning);
  }

  .blocking .finding-icon {
    color: var(--lc-danger);
  }

  li > header > div {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  li code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .severity {
    color: var(--lc-muted);
    font-size: 10px;
    font-weight: 780;
  }

  li p {
    margin: var(--lc-space-2) 0 0 26px;
    color: var(--lc-text);
    font-size: 12px;
    line-height: 1.55;
  }

  dl {
    display: grid;
    gap: 6px;
    margin: var(--lc-space-3) 0 0 26px;
  }

  dl > div {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(110px, 0.3fr) minmax(0, 1fr);
    gap: var(--lc-space-2);
  }

  dt,
  dd {
    margin: 0;
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-size: 11px;
  }

  @media (max-width: 760px) {
    dl > div {
      grid-template-columns: 1fr;
    }

    li p,
    dl {
      margin-left: 0;
    }
  }
</style>
