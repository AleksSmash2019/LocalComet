<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import ReviewPanel from './ReviewPanel.svelte';
  import { sortReviewFindings } from '$lib/types/knowledgeReview';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  $: findings = sortReviewFindings(review.findings);
</script>

<ReviewPanel
  headingId="review-findings-heading"
  eyebrowKey="review.findings.eyebrow"
  titleKey="review.findings.title"
>
  <span slot="header-aside" class="finding-count">{findings.length}</span>

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
</ReviewPanel>

<style>
  /* Panel frame styles live in ReviewPanel.svelte. */
</style>
