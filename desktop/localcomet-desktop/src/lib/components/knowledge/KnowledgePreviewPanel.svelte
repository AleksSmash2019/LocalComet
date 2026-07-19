<svelte:window onkeydown={(event) => {
  if (event.key === 'Escape' && $knowledgePreviewStore.lifecycle === 'PREVIEW_READY') void cancelProjectKnowledge();
}} />

<script lang="ts">
  import { t } from '$lib/i18n';
  import { abbreviateKnowledgeHash } from '$lib/knowledge/knowledgePreview';
  import {
    cancelProjectKnowledge,
    decideProjectKnowledge,
    knowledgePreviewStore,
    retryProjectKnowledgePreview,
    sendWithoutKnowledgeAfterFailure,
    toggleKnowledgeSource
  } from '$lib/stores/knowledgePreview';
  import KnowledgeSourceCard from './KnowledgeSourceCard.svelte';
  import KnowledgeStatusBadge from './KnowledgeStatusBadge.svelte';

  $: state = $knowledgePreviewStore;
  $: preview = state.preview;
</script>

{#if state.enabled && state.lifecycle !== 'OFF'}
  <section class="preview-panel" aria-label={$t('knowledge.approval_label')} aria-live="polite">
    <header>
      <div>
        <h3>{$t('knowledge.title')}</h3>
        {#if preview}
          <p>{preview.source_count} {$t('knowledge.sources')} · {preview.total_chars.toLocaleString()} {$t('knowledge.characters')} · {$t('knowledge.vault')} {abbreviateKnowledgeHash(preview.vault_revision)}</p>
        {/if}
      </div>
      <KnowledgeStatusBadge state={state.lifecycle} />
    </header>

    {#if state.lifecycle === 'RETRIEVING'}
      <p class="message">{$t('knowledge.retrieving')}</p>
    {:else if preview}
      <div class="sources">
        {#each preview.sources as source (source.note_id)}
          <KnowledgeSourceCard source={source} expanded={state.expandedSourceIds.includes(source.note_id)} onToggle={() => toggleKnowledgeSource(source.note_id)} />
        {/each}
      </div>
    {/if}

    {#if state.lastError}
      <p class="error" role="alert">{state.lifecycle === 'STALE' ? $t('knowledge.stale_message') : $t('knowledge.failure_message')}</p>
    {/if}

    <footer>
      {#if state.lifecycle === 'PREVIEW_READY'}
        <button class="primary" type="button" onclick={() => void decideProjectKnowledge('INCLUDE_AND_SEND')}>{$t('knowledge.include_send')}</button>
        <button type="button" onclick={() => void decideProjectKnowledge('REJECT_AND_SEND_WITHOUT_KNOWLEDGE')}>{$t('knowledge.send_without')}</button>
        <button type="button" onclick={() => void cancelProjectKnowledge()}>{$t('knowledge.cancel')}</button>
      {:else if state.lifecycle === 'FAILED' || state.lifecycle === 'STALE'}
        <button class="primary" type="button" onclick={() => void retryProjectKnowledgePreview()}>{$t(state.lifecycle === 'STALE' ? 'knowledge.refresh' : 'knowledge.retry')}</button>
        <button type="button" onclick={() => void sendWithoutKnowledgeAfterFailure()}>{$t('knowledge.send_without')}</button>
        <button type="button" onclick={() => void cancelProjectKnowledge()}>{$t('knowledge.cancel')}</button>
      {/if}
    </footer>
  </section>
{/if}

<style>
  .preview-panel { width: min(calc(100% - 48px), var(--content-width)); max-height: min(52vh, 620px); margin: 0 auto var(--lc-space-3); padding: var(--lc-space-4); overflow: auto; border: 1px solid rgb(120 255 152 / 42%); border-radius: var(--lc-radius); background: color-mix(in srgb, var(--lc-panel) 96%, #78ff98 4%); box-shadow: 0 0 24px rgb(120 255 152 / 8%); }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--lc-space-3); }
  h3 { margin: 0; color: var(--lc-text); font-size: .95rem; }
  p { margin: 5px 0 0; color: var(--lc-muted); font-size: .72rem; }
  .sources { display: grid; gap: var(--lc-space-2); margin-top: var(--lc-space-3); }
  .message { padding: var(--lc-space-4) 0; }
  .error { color: #ff9292; }
  footer { display: flex; flex-wrap: wrap; gap: var(--lc-space-2); margin-top: var(--lc-space-3); }
  footer:empty { display: none; }
  footer button { min-height: 38px; padding: 7px 12px; border: 1px solid var(--lc-border); border-radius: var(--lc-radius-sm); background: var(--lc-panel-soft); color: var(--lc-text); cursor: pointer; font-weight: 720; }
  footer button.primary { border-color: #78ff98; background: #78ff98; color: #071009; }
  footer button:focus-visible { outline: 2px solid #78ff98; outline-offset: 2px; }
  @media (max-width: 760px) { .preview-panel { width: calc(100% - 24px); max-height: 58vh; padding: var(--lc-space-3); } header { align-items: center; } footer button { flex: 1 1 100%; } }
</style>
