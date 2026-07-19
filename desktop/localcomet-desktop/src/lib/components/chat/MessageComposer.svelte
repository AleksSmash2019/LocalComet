<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import KnowledgePreviewPanel from '$lib/components/knowledge/KnowledgePreviewPanel.svelte';
  import KnowledgeToggle from '$lib/components/knowledge/KnowledgeToggle.svelte';
  import { appendMockMessage, composerDraft, setComposerDraft } from '$lib/stores/shellStore';
  import { modelGatewayStore } from '$lib/stores/modelGateway';
  import { modelConnected } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';
  import { createPendingKnowledgeTurn, controlPlaneStore } from '$lib/stores/controlPlane';
  import { knowledgePreviewStore, prepareProjectKnowledge } from '$lib/stores/knowledgePreview';
  import { startLocalModelTurn } from '$lib/stores/modelGateway';

  let textarea: HTMLTextAreaElement;

  $: knowledgeLocked = ['RETRIEVING', 'PREVIEW_READY', 'DECIDING', 'DISPATCHING'].includes($knowledgePreviewStore.lifecycle);
  $: canSend = $modelConnected && Boolean($composerDraft.trim()) && !knowledgeLocked && (!$knowledgePreviewStore.enabled || $controlPlaneStore.bridgeState === 'READY');
  $: isGenerating = $modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Cancelling';

  function resizeDraftBox(): void {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
  }

  async function send(): Promise<void> {
    if (!canSend) return;
    const draft = $composerDraft;
    if ($knowledgePreviewStore.enabled) {
      const turn = await createPendingKnowledgeTurn(draft);
      if (!turn) return;
      if (!appendMockMessage(draft)) return;
      resizeDraftBox();
      await prepareProjectKnowledge(turn.turn_id, draft);
      return;
    }
    if (!appendMockMessage(draft)) return;
    resizeDraftBox();
    await startLocalModelTurn(draft);
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }
</script>

<KnowledgePreviewPanel />
<form class="composer-wrap" aria-label={$t('chat.type_message')} onsubmit={(event) => event.preventDefault()}>
  <KnowledgeToggle />
  <div class="composer card-surface">
    <div class="tools-wrap">
      <button
        type="button"
        class="icon-button"
        aria-label={$t('chat.tools_unavailable')}
        disabled
      >
        <Icon name="tool" />
      </button>
    </div>

    <label class="sr-only" for="composer-draft">{$t('chat.type_message')}</label>
    <textarea
      id="composer-draft"
      bind:this={textarea}
      value={$composerDraft}
      maxlength="12000"
      rows="1"
      placeholder={$modelConnected ? ($modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Cancelling' ? $t('chat.model_responding') : $t('chat.type_message')) : $t('chat.connect_model_first')}
      disabled={!$modelConnected || isGenerating || knowledgeLocked}
      oninput={(event) => {
        setComposerDraft(event.currentTarget.value);
        resizeDraftBox();
      }}
      onkeydown={handleKeydown}
    ></textarea>

    <button type="button" class="send-button" disabled={!canSend} onclick={() => void send()}>
      <span>{$modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Cancelling' ? $t('chat.stop') : $t('chat.send')}</span>
      <Icon name={$modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Cancelling' ? 'stop' : 'send'} size={18} />
    </button>
  </div>
</form>

<style>
  .composer-wrap {
    width: min(calc(100% - 48px), var(--content-width));
    margin: 0 auto var(--lc-space-4);
    z-index: 10;
  }

  .composer {
    min-height: 66px;
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) auto;
    align-items: end;
    gap: var(--lc-space-2);
    padding: var(--lc-space-3);
    box-shadow: var(--lc-shadow);
  }

  .icon-button {
    width: 40px;
    display: grid;
    place-items: center;
  }

  .tools-wrap {
    position: relative;
  }

  textarea {
    min-height: 40px;
    max-height: 150px;
    resize: none;
    overflow-y: auto;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--lc-text);
    line-height: 1.5;
    padding: var(--lc-space-2) 0;
  }

  textarea:disabled {
    color: var(--lc-faint);
  }

  .send-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    min-width: 84px;
    border: 0;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: #071009;
    font-weight: 820;
    cursor: pointer;
  }

  .send-button:disabled {
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
  }

  @media (max-width: 760px) {
    .composer-wrap {
      width: calc(100% - 24px);
    }
  }
</style>
