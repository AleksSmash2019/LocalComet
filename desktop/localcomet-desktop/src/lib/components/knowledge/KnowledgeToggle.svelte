<script lang="ts">
  import { t } from '$lib/i18n';
  import { knowledgePreviewStore, setProjectKnowledgeEnabled } from '$lib/stores/knowledgePreview';

  $: locked = ['RETRIEVING', 'PREVIEW_READY', 'DECIDING', 'DISPATCHING'].includes($knowledgePreviewStore.lifecycle);
</script>

<div class="knowledge-toggle">
  <div>
    <strong>{$t('knowledge.title')}</strong>
    <span>{$t($knowledgePreviewStore.enabled ? 'knowledge.enabled' : 'knowledge.disabled')}</span>
  </div>
  <button
    type="button"
    role="switch"
    aria-label={$t('knowledge.toggle_label')}
    aria-checked={$knowledgePreviewStore.enabled}
    disabled={locked}
    class:enabled={$knowledgePreviewStore.enabled}
    onclick={() => setProjectKnowledgeEnabled(!$knowledgePreviewStore.enabled)}
  >
    <span></span>
  </button>
</div>

<style>
  .knowledge-toggle { display: flex; align-items: center; justify-content: space-between; gap: var(--lc-space-3); padding: 0 var(--lc-space-2) var(--lc-space-2); }
  .knowledge-toggle div { display: flex; align-items: baseline; gap: var(--lc-space-2); min-width: 0; }
  strong { color: var(--lc-text); font-size: .82rem; }
  .knowledge-toggle div span { color: var(--lc-muted); font-size: .72rem; }
  button { position: relative; width: 40px; height: 22px; flex: 0 0 auto; padding: 2px; border: 1px solid var(--lc-border); border-radius: 999px; background: var(--lc-panel-soft); cursor: pointer; }
  button span { display: block; width: 16px; height: 16px; border-radius: 50%; background: var(--lc-muted); transition: transform .15s ease, background .15s ease; }
  button.enabled { border-color: #78ff98; box-shadow: 0 0 12px rgb(120 255 152 / 12%); }
  button.enabled span { transform: translateX(17px); background: #78ff98; }
  button:disabled { cursor: not-allowed; opacity: .55; }
  button:focus-visible { outline: 2px solid #78ff98; outline-offset: 2px; }
</style>
