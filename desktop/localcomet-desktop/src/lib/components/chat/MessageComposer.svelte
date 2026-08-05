<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import KnowledgeToggle from '$lib/components/knowledge/KnowledgeToggle.svelte';
  import FilesPanel from '$lib/components/files/FilesPanel.svelte';
  import { composerDraft, openSettings, selectedConversationId, setComposerDraft } from '$lib/stores/shellStore';
  import { applyAutoTitle } from '$lib/stores/conversationStore';
  import { t } from '$lib/i18n';
  import { cancelLocalModelTurn, inferenceRequestStore, managedModelReady, startLocalModelTurn } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';
  import { includedFileIds, addFiles } from '$lib/stores/files';

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
    applyAutoTitle($selectedConversationId, draft);
    await startLocalModelTurn(draft, $selectedConversationId, $includedFileIds);
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
    <FilesPanel />
    <KnowledgeToggle />
    <div class="composer pill-surface">
      <button type="button" class="composer-icon-button" aria-label={$t('files.add')} title={$t('files.add')} onclick={() => void addFiles()}>
        <Icon name="attach" size={20} />
      </button>

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

      <button type="button" class="composer-icon-button" aria-label="Искать" title="Искать" onclick={() => {}}>
        <Icon name="search" size={18} />
      </button>

      <button
        type="button"
        class="send-button pill-send"
        aria-label={$t(isGenerating ? 'chat.stop' : 'chat.send')}
        title={$t(isGenerating ? 'chat.stop' : 'chat.send')}
        disabled={isGenerating ? false : !canSend}
        onclick={() => void send()}
      >
        <Icon name={isGenerating ? 'stop' : 'send'} size={18} />
      </button>
    </div>
    {#if $inferenceRequestStore.lastError}
      <p class="request-error" role="status">{$t(requestErrorKey)}</p>
    {/if}
    {#if !$managedModelReady && !isGenerating}
      <div class="first-use" style="display: none;" role="status">
        <strong>{$t('chat.model_not_connected')}</strong>
        <div>
          <button type="button" class="setup-button" onclick={() => openSettings('models')}>{$t('chat.setup_local_ai')}</button>
          <button type="button" class="models-button" onclick={() => openSettings('models')}>{$t('chat.open_models')}</button>
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
    margin: 0 auto 16px;
    z-index: 10;
  }

  .composer {
    min-height: 52px;
    display: flex;
    align-items: flex-end;
    gap: 8px;
    border: 1px solid var(--lc-line);
    border-radius: 26px; /* Pill shape */
    padding: 6px 8px;
    background: var(--lc-panel);
    box-shadow: var(--lc-shadow-e1);
  }

  .composer-icon-button {
    width: 36px;
    height: 36px;
    min-height: 36px;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--lc-muted);
    cursor: pointer;
    margin-bottom: 2px;
  }

  .composer-icon-button:hover {
    background: var(--lc-panel-soft);
    color: var(--lc-text);
  }

  .send-button.pill-send {
    width: 36px;
    height: 36px;
    min-height: 36px;
    padding: 0;
    display: grid;
    place-items: center;
    border-radius: 50%;
    margin-bottom: 2px;
  }
  
  .send-button.pill-send span {
    display: none;
  }

  textarea {
    flex: 1;
    min-width: 0;
    min-height: 24px;
    max-height: 200px;
    margin-bottom: 8px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--lc-text);
    font-size: 15px;
    line-height: 1.5;
    resize: none;
    outline: none;
  }

  textarea:disabled {
    color: var(--lc-muted);
    cursor: not-allowed;
  }

  textarea::placeholder {
    color: var(--lc-faint);
  }

  .send-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    min-width: 88px;
    min-height: 40px;
    border: 0;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: #071009;
    font-size: 14px;
    font-weight: 650;
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
    border-radius: var(--lc-radius-lg);
    padding: 10px 12px;
    background: color-mix(in srgb, var(--lc-panel-solid) 50%, transparent);
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

  .composer-wrap :global(.files-panel) {
    gap: 8px;
    margin-bottom: 6px;
    border-color: color-mix(in srgb, var(--lc-line) 72%, transparent);
    border-radius: var(--lc-radius-lg);
    padding: 8px 10px;
    background: color-mix(in srgb, var(--lc-panel-solid) 48%, transparent);
  }

  .composer-wrap :global(.knowledge-availability) {
    padding: 2px 8px 7px;
  }

  @media (max-width: 760px) {
    .composer-wrap {
      width: calc(100% - 24px);
    }
  }
</style>
