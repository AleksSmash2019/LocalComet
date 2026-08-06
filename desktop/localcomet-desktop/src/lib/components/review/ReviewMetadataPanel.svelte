<script lang="ts">
  import { t } from '$lib/i18n';
  import ReviewPanel from './ReviewPanel.svelte';
  import {
    PROPOSED_CONTENT_FIELDS,
    type MetadataChange,
    type MetadataValue,
    type ProposedContentField,
    type ReviewCenterItem
  } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  function formatValue(value: MetadataValue): string {
    if (value === null) return 'null';
    if (typeof value === 'string') return value;
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return JSON.stringify(value);
  }

  function fieldValue(field: ProposedContentField): MetadataValue {
    return review.proposedContent[field];
  }

  function changeFor(field: ProposedContentField): MetadataChange | undefined {
    return review.metadataChanges.find((change) => change.field === field);
  }
</script>

<ReviewPanel
  headingId="review-metadata-heading"
  eyebrowKey="review.metadata.eyebrow"
  titleKey="review.metadata.title"
>
  <span slot="header-aside" class="field-count">
    {PROPOSED_CONTENT_FIELDS.length} {$t('review.metadata.fields')}
  </span>

  <p class="metadata-note">{$t('review.metadata.projection_note')}</p>

  <dl class="metadata-list">
    {#each PROPOSED_CONTENT_FIELDS as field}
      {@const change = changeFor(field)}
      <div class:changed={Boolean(change)} class="metadata-row">
        <dt>
          <code>{field}</code>
          <span>{$t(`review.metadata.field.${field}`)}</span>
        </dt>
        <dd>
          <pre>{formatValue(fieldValue(field))}</pre>
          {#if change}
            <div class="change-detail" aria-label={$t('review.metadata.changed')}>
              <div>
                <span>{$t('review.metadata.before')}</span>
                <code>{formatValue(change.before)}</code>
              </div>
              <div>
                <span>{$t('review.metadata.after')}</span>
                <code>{formatValue(change.after)}</code>
              </div>
            </div>
          {/if}
        </dd>
      </div>
    {/each}
  </dl>
</ReviewPanel>

<style>
  /* Panel frame styles live in ReviewPanel.svelte. */
  .field-count {
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .metadata-note {
    margin: 0 0 var(--lc-space-4);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: var(--lc-space-3);
    font-size: 12px;
    line-height: 1.5;
  }

  .metadata-list {
    display: grid;
    gap: 0;
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    overflow: hidden;
  }

  .metadata-row {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(170px, 0.32fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-3);
  }

  .metadata-row:last-child {
    border-bottom: 0;
  }

  .metadata-row.changed {
    box-shadow: inset 3px 0 0 var(--lc-warning);
  }

  dt,
  dd {
    min-width: 0;
    margin: 0;
  }

  dt {
    display: grid;
    align-content: start;
    gap: 4px;
  }

  dt code {
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
    overflow-wrap: anywhere;
  }

  dt span {
    color: var(--lc-muted);
    font-size: 11px;
  }

  pre {
    max-height: 180px;
    overflow: auto;
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .change-detail {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-3);
  }

  .change-detail > div {
    min-width: 0;
    display: grid;
    gap: 4px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    padding: var(--lc-space-2);
  }

  .change-detail span {
    color: var(--lc-warning);
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
  }

  .change-detail code {
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  @media (max-width: 760px) {
    .metadata-row {
      grid-template-columns: 1fr;
    }

    .change-detail {
      grid-template-columns: 1fr;
    }
  }
</style>
