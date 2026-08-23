<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import KnowledgeToggle from '$lib/components/knowledge/KnowledgeToggle.svelte';
  import EffortSelector from '$lib/components/chat/EffortSelector.svelte';
  import FilesPanel from '$lib/components/files/FilesPanel.svelte';
  import { composerDraft, openSettings, selectedConversationId, setComposerDraft } from '$lib/stores/shellStore';
  import { applyAutoTitle } from '$lib/stores/conversationStore';
  import { t } from '$lib/i18n';
  import {
    approvedManagedModelInstalled,
    cancelLocalModelTurn,
    connectSelectedManagedModel,
    inferenceRequestStore,
    managedConnectionBusy,
    managedModelReady,
    startLocalModelTurn
  } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';
  import { includedFileIds, addFiles } from '$lib/stores/files';
  import { voiceMode, setVoiceMode } from '$lib/stores/shellStore';
  import { stopLocalText } from '$lib/bridge/voice';

  let textarea: HTMLTextAreaElement;
  let restoreComposerFocus = false;
  let previouslyGenerating = false;
  let observedConversationId = $selectedConversationId;
  let isListening = false;
  let recognition: any = null;
  let voiceNotice = '';

  $: isGenerating = ['submitted', 'accepted', 'streaming', 'awaiting_approval', 'awaiting_verification', 'cancelling'].includes($inferenceRequestStore.lifecycle);
  $: if ($selectedConversationId !== observedConversationId) {
    observedConversationId = $selectedConversationId;
    setComposerDraft('');
    if (isGenerating) void cancelLocalModelTurn();
  }
  $: canSend = $managedModelReady && Boolean($composerDraft.trim()) && !isGenerating;
  $: {
    const generatingNow = isGenerating;
    if (previouslyGenerating && !generatingNow) {
      void restoreFocusAfterRequest();
    }
    previouslyGenerating = generatingNow;
  }

  async function toggleVoiceMode(): Promise<void> {
    const enabled = !$voiceMode;
    setVoiceMode(enabled);
    voiceNotice = '';
    if (!enabled) {
      const stopped = await stopLocalText();
      if (!stopped) voiceNotice = $t('chat.speech_stop_failed');
    }
  }

  function startListening() {
    voiceNotice = '';
    if (isListening) {
      recognition?.stop();
      isListening = false;
      return;
    }
    if (!$managedModelReady || isGenerating) {
      recognition?.abort();
      recognition = null;
      isListening = false;
      setComposerDraft('');
      resizeDraftBox();
      return;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      voiceNotice = $t('chat.speech_unsupported');
      return;
    }
    recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.continuous = false;
    recognition.interimResults = true;
    let finalTranscript = '';
    let interimTranscript = '';
    let autoSendStarted = false;
    recognition.onresult = (event: any) => {
      interimTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const result = event.results[i];
        const fragment = String(result?.[0]?.transcript || '').trim();
        if (!fragment) continue;
        if (result.isFinal) finalTranscript = `${finalTranscript} ${fragment}`.trim();
        else interimTranscript = `${interimTranscript} ${fragment}`.trim();
      }
      const transcript = `${finalTranscript} ${interimTranscript}`.trim();
      if (!$managedModelReady || isGenerating) {
        recognition?.abort();
        recognition = null;
        isListening = false;
        setComposerDraft('');
        resizeDraftBox();
        return;
      }
      setComposerDraft(transcript);
      resizeDraftBox();
      if (finalTranscript && !autoSendStarted) {
        autoSendStarted = true;
        isListening = false;
        recognition.stop();
        void send(finalTranscript);
      }
    };
    recognition.onerror = () => {
      isListening = false;
      recognition = null;
      if (!$managedModelReady || isGenerating) {
        setComposerDraft('');
        resizeDraftBox();
      }
    };
    recognition.onend = () => {
      isListening = false;
      recognition = null;
      if (!$managedModelReady || isGenerating) {
        setComposerDraft('');
        resizeDraftBox();
      }
    };
    recognition.start();
    isListening = true;
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

  async function send(draftOverride?: string): Promise<void> {
    if (isGenerating) {
      restoreComposerFocus = true;
      await cancelLocalModelTurn();
      await restoreFocusAfterRequest();
      return;
    }
    const draft = (draftOverride ?? $composerDraft).trim();
    if (!draft || isGenerating) return;
    if (!$managedModelReady) {
      if (draftOverride) {
        setComposerDraft('');
        resizeDraftBox();
      }
      return;
    }
    restoreComposerFocus = true;
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
    <!--
      No connect button here: the empty-state card above the composer already
      offers the single "Set up local AI" action, so a second control would be
      a duplicate.
    -->
    <div class="composer pill-surface">
      <div class="composer-actions composer-actions-left">
        <EffortSelector />

        <button type="button" class="composer-icon-button" aria-label={$t('files.add')} title={$t('files.add')} onclick={() => void addFiles()}>
          <Icon name="attach" size={19} />
        </button>
      </div>

      <div class="composer-input">
        <label class="sr-only" for="composer-draft">{$t('chat.type_message')}</label>
        <textarea
          id="composer-draft"
          bind:this={textarea}
          value={$composerDraft}
          maxlength="12000"
          rows="1"
          placeholder={$managedModelReady ? ($inferenceRequestStore.lifecycle === 'awaiting_approval' ? $t('chat.awaiting_approval') : $inferenceRequestStore.lifecycle === 'awaiting_verification' ? $t('chat.awaiting_verification') : isGenerating ? $t('chat.model_responding') : $t('chat.type_message')) : $acquisitionBusy ? $t('chat.model_installing') : $t('chat.connect_model_first')}
          disabled={!$managedModelReady || isGenerating}
          oninput={(event) => {
            setComposerDraft(event.currentTarget.value);
            resizeDraftBox();
          }}
          onkeydown={handleKeydown}
        ></textarea>
      </div>

      <div class="composer-actions composer-actions-right">
        <button type="button" class="composer-icon-button" class:active-control={$voiceMode} aria-pressed={$voiceMode} aria-label={$t($voiceMode ? 'chat.voice_output_disable' : 'chat.voice_output_enable')} title={$t($voiceMode ? 'chat.voice_output_disable' : 'chat.voice_output_enable')} onclick={() => void toggleVoiceMode()}>
          <Icon name="audio" size={19} />
        </button>

        <button
          type="button"
          class="composer-icon-button"
          class:recording={isListening}
          aria-pressed={isListening}
          aria-label={$t('chat.voice_input')}
          title={$t('chat.voice_input')}
          disabled={!$managedModelReady || isGenerating}
          onclick={startListening}
          style="color: {isListening ? 'var(--lc-danger)' : 'var(--lc-muted)'};"
        >
          <Icon name="microphone" size={19} />
        </button>

        <button
          type="button"
          class="send-button pill-send"
          aria-label={$t(isGenerating ? 'chat.stop' : 'chat.send')}
          title={$t(isGenerating ? 'chat.stop' : 'chat.send')}
          disabled={isGenerating ? false : !canSend}
          onclick={() => void send()}
        >
          <Icon name={isGenerating ? 'stop' : 'send'} size={16} />
        </button>
      </div>
    </div>
    {#if voiceNotice}
      <p class="composer-notice" role="status">{voiceNotice}</p>
    {/if}
    {#if $composerDraft.length > 500}
      <div class="char-counter" class:warn={$composerDraft.length > 10000}>
        {$composerDraft.length} / 12000
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
    display: flex;
    align-items: flex-end;
    gap: 6px;
    border: 1px solid color-mix(in srgb, var(--lc-line) 60%, transparent);
    border-radius: 16px;
    padding: 10px 14px;
    background: color-mix(in srgb, var(--lc-panel-soft) 40%, transparent);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow: var(--lc-shadow-e1);
    transition: box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease;
  }

  .composer:hover:not(:focus-within) {
    background: color-mix(in srgb, var(--lc-panel-soft) 55%, transparent);
    border-color: color-mix(in srgb, var(--lc-line) 90%, transparent);
  }

  .composer:focus-within {
    border-color: color-mix(in srgb, var(--lc-accent) 62%, var(--lc-line));
    background: color-mix(in srgb, var(--lc-panel-soft) 58%, transparent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--lc-accent) 12%, transparent), var(--lc-shadow-e1);
  }

  .composer button:focus,
  .composer textarea:focus {
    outline: none;
    box-shadow: none;
  }

  .composer-actions {
    display: inline-flex;
    align-items: flex-end;
    flex: 0 0 auto;
    gap: 4px;
    min-width: 0;
  }

  .composer-input {
    display: flex;
    align-items: flex-end;
    flex: 1 1 auto;
    min-width: 0;
  }

  .composer-icon-button {
    width: 34px;
    height: 34px;
    min-height: 34px;
    flex: 0 0 34px;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--lc-muted);
    cursor: pointer;
    margin-bottom: 2px;
    transition: color 0.2s ease, background 0.2s ease, transform 0.2s ease;
  }

  .composer-icon-button:hover {
    background: color-mix(in srgb, var(--lc-panel-soft) 80%, transparent);
    color: var(--lc-text);
    transform: translateY(-1px);
  }

  .composer-icon-button:disabled {
    cursor: not-allowed;
    opacity: 0.48;
    transform: none;
  }

  .composer-icon-button.recording {
    animation: pulse-mic 1.5s infinite ease-in-out;
  }

  .composer-icon-button.active-control {
    background: var(--lc-accent-dim);
    color: var(--lc-accent-strong);
  }

  @keyframes pulse-mic {
    0%, 100% {
      transform: scale(1);
      background: color-mix(in srgb, var(--lc-danger) 15%, transparent);
    }
    50% {
      transform: scale(1.15);
      background: color-mix(in srgb, var(--lc-danger) 30%, transparent);
      box-shadow: 0 0 10px color-mix(in srgb, var(--lc-danger) 40%, transparent);
    }
  }

  .send-button.pill-send {
    width: 32px;
    min-width: 32px;
    flex: 0 0 32px;
    height: 32px;
    min-height: 32px;
    padding: 0;
    display: grid;
    place-items: center;
    border-radius: 50%;
    margin-bottom: 2px;
  }

  textarea {
    flex: 1;
    min-width: 0;
    min-height: 24px;
    width: 100%;
    max-height: 240px;
    margin-bottom: 6px;
    margin-top: 6px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--lc-text);
    font-size: 15.5px;
    line-height: 1.6;
    resize: none;
    outline: none;
    overflow-y: auto;
    scrollbar-width: none;
  }

  textarea::-webkit-scrollbar {
    width: 0;
    height: 0;
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
    color: var(--lc-logo-cut);
    font-size: 14px;
    font-weight: 650;
    cursor: pointer;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.2s ease, box-shadow 0.2s ease;
  }

  .send-button:not(:disabled):hover {
    transform: scale(1.05);
    background: var(--lc-accent-strong);
    box-shadow: 0 4px 12px color-mix(in srgb, var(--lc-accent) 40%, transparent);
  }

  .send-button:disabled {
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
  }

  .char-counter {
    text-align: right;
    font-size: 11px;
    color: var(--lc-faint);
    font-family: var(--lc-mono);
    margin-top: 4px;
    padding-right: 12px;
  }

  .char-counter.warn {
    color: var(--lc-warning);
    font-weight: 600;
  }

  .composer-notice {
    margin: 8px 8px 0;
    color: var(--lc-warning);
    font-size: 12px;
    line-height: 1.45;
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

    .composer {
      gap: 4px;
      padding: 8px 10px;
    }

    .composer-actions {
      gap: 2px;
    }

    .composer-icon-button {
      width: 32px;
      min-width: 32px;
      height: 32px;
      min-height: 32px;
      flex-basis: 32px;
    }
  }
</style>
