<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import KnowledgePreviewPanel from '$lib/components/knowledge/KnowledgePreviewPanel.svelte';
  import KnowledgeToggle from '$lib/components/knowledge/KnowledgeToggle.svelte';
  import { appendMockMessage, composerDraft, selectedConversationId, setComposerDraft } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';
  import { createPendingKnowledgeTurn, controlPlaneStore } from '$lib/stores/controlPlane';
  import { knowledgePreviewStore, prepareProjectKnowledge } from '$lib/stores/knowledgePreview';
  import { cancelLocalModelTurn, inferenceRequestStore, managedModelReady, startLocalModelTurn } from '$lib/stores/modelGateway';

  let textarea: HTMLTextAreaElement;
  let restoreComposerFocus = false;
  let previouslyGenerating = false;

  $: knowledgeLocked = ['RETRIEVING', 'PREVIEW_READY', 'DECIDING', 'DISPATCHING'].includes($knowledgePreviewStore.lifecycle);
  $: isGenerating = ['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle);
  $: canSend = $managedModelReady && Boolean($composerDraft.trim()) && !isGenerating && !knowledgeLocked && (!$knowledgePreviewStore.enabled || $controlPlaneStore.bridgeState === 'READY');
  $: firstTokenMs = $inferenceRequestStore.submittedAtUnixMs && $inferenceRequestStore.firstTokenAtUnixMs
    ? Math.max(0, $inferenceRequestStore.firstTokenAtUnixMs - $inferenceRequestStore.submittedAtUnixMs)
    : null;
  $: totalMs = $inferenceRequestStore.submittedAtUnixMs && $inferenceRequestStore.terminalAtUnixMs
    ? Math.max(0, $inferenceRequestStore.terminalAtUnixMs - $inferenceRequestStore.submittedAtUnixMs)
    : null;
  $: {
    const generatingNow = isGenerating;
    if (previouslyGenerating && !generatingNow) {
      void restoreFocusAfterRequest();
    }
    previouslyGenerating = generatingNow;
  }

  async function restoreFocusAfterRequest(): Promise<void> {
    if (!restoreComposerFocus) return;
    await tick();
    const active = document.activeElement;
    const focusRemainedInComposer =
      !active ||
      active === document.body ||
      active === document.documentElement ||
      active === textarea ||
      (active instanceof HTMLElement && Boolean(active.closest('.composer-region')));
    if (!focusRemainedInComposer) {
      restoreComposerFocus = false;
      return;
    }
    if (!textarea || textarea.disabled) return;
    restoreComposerFocus = false;
    textarea.focus({ preventScroll: true });
  }

  function resizeDraftBox(): void {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
  }

  async function send(): Promise<void> {
    if (isGenerating) {
      restoreComposerFocus = true;
      await cancelLocalModelTurn();
      await restoreFocusAfterRequest();
      return;
    }
    if (!canSend) return;
    restoreComposerFocus = true;
    const draft = $composerDraft;
    if ($knowledgePreviewStore.enabled) {
      const turn = await createPendingKnowledgeTurn(draft);
      if (!turn) return;
      if (!appendMockMessage(draft)) return;
      resizeDraftBox();
      await prepareProjectKnowledge(turn.turn_id, draft);
      return;
    }
    await startLocalModelTurn(draft, $selectedConversationId);
    await restoreFocusAfterRequest();
    resizeDraftBox();
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }
</script>

<div class="composer-region">
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
        placeholder={$managedModelReady ? (isGenerating ? $t('chat.model_responding') : $t('chat.type_message')) : $t('chat.connect_model_first')}
        disabled={!$managedModelReady || isGenerating || knowledgeLocked}
        oninput={(event) => {
          setComposerDraft(event.currentTarget.value);
          resizeDraftBox();
        }}
        onkeydown={handleKeydown}
      ></textarea>

      <button type="button" class="send-button" disabled={isGenerating ? false : !canSend} onclick={() => void send()}>
        <span>{isGenerating ? $t('chat.stop') : $t('chat.send')}</span>
        <Icon name={isGenerating ? 'stop' : 'send'} size={18} />
      </button>
    </div>
    {#if $inferenceRequestStore.lastError}
      <p class="request-error" role="status">{$inferenceRequestStore.lastError.message}</p>
    {/if}
    {#if $inferenceRequestStore.requestId}
      <p class="request-metrics" data-request-id={$inferenceRequestStore.requestId}>
        {$inferenceRequestStore.lifecycle} · chunks {$inferenceRequestStore.chunkCount} · first {firstTokenMs ?? '—'} ms · total {totalMs ?? '—'} ms
      </p>
    {/if}
  </form>
</div>

<style>
  .composer-region {
    min-width: 0;
    min-height: 0;
    flex: 0 0 auto;
  }

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
    width: 100%;
    min-width: 0;
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

  .request-error {
    margin: var(--lc-space-2) 0 0;
    color: var(--lc-danger);
    font-size: 12px;
    font-weight: 700;
  }

  .request-metrics {
    margin: var(--lc-space-2) 0 0;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  @media (max-width: 760px) {
    .composer-wrap {
      width: calc(100% - 24px);
    }
  }
</style>
