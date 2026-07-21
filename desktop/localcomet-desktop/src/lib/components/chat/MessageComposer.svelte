<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import KnowledgeToggle from '$lib/components/knowledge/KnowledgeToggle.svelte';
  import { composerDraft, openSettings, selectedConversationId, setComposerDraft } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';
  import { cancelLocalModelTurn, inferenceRequestStore, managedModelReady, startLocalModelTurn } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';

  let textarea: HTMLTextAreaElement;
  let restoreComposerFocus = false;
  let previouslyGenerating = false;

  $: isGenerating = ['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle);
  $: canSend = $managedModelReady && Boolean($composerDraft.trim()) && !isGenerating;
  $: requestErrorKey = $inferenceRequestStore.lifecycle === 'timed_out'
    ? 'chat.request_timed_out_detail'
    : 'chat.request_failed_detail';
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
  <form class="composer-wrap" aria-label={$t('chat.type_message')} onsubmit={(event) => event.preventDefault()}>
    <KnowledgeToggle />
    <div class="composer card-surface">
      <label class="sr-only" for="composer-draft">{$t('chat.type_message')}</label>
      <textarea
        id="composer-draft"
        bind:this={textarea}
        value={$composerDraft}
        maxlength="12000"
        rows="1"
        placeholder={$managedModelReady ? (isGenerating ? $t('chat.model_responding') : $t('chat.type_message')) : $acquisitionBusy ? $t('chat.model_installing') : $t('chat.connect_model_first')}
        disabled={!$managedModelReady || isGenerating}
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
      <p class="request-error" role="status">{$t(requestErrorKey)}</p>
    {/if}
    {#if !$managedModelReady && !isGenerating}
      <div class="first-use" role="status">
        <strong>{$t('chat.model_not_connected')}</strong>
        <p>{$acquisitionBusy ? $t('chat.model_loading_detail') : $t('chat.model_not_connected_detail')}</p>
        <div>
          <button type="button" class="setup-button" onclick={openSettings}>{$t('chat.setup_local_ai')}</button>
          <button type="button" class="models-button" onclick={openSettings}>{$t('chat.open_models')}</button>
        </div>
      </div>
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
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: var(--lc-space-2);
    padding: var(--lc-space-3);
    box-shadow: var(--lc-shadow);
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

  .first-use {
    display: grid;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
    font-size: 12px;
  }

  .first-use p {
    margin: 0;
    color: var(--lc-muted);
    line-height: 1.45;
  }

  .first-use > div {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .setup-button,
  .models-button {
    min-height: 34px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: 0 var(--lc-space-3);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .setup-button {
    border-color: var(--lc-accent);
    background: var(--lc-accent);
    color: #071009;
  }

  .models-button {
    background: var(--lc-panel-solid);
    color: var(--lc-text);
  }

  @media (max-width: 760px) {
    .composer-wrap {
      width: calc(100% - 24px);
    }
  }
</style>
