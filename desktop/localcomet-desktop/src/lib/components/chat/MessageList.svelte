<script lang="ts">
  import EmptyState from '$lib/components/common/EmptyState.svelte';
  import { chatMessages, composerDraft, openModelSetup, selectedConversationId, setComposerDraft } from '$lib/stores/shellStore';
  import {
    inferenceBusy,
    inferenceRequestStore,
    managedModelReady,
    managedRuntimeStore,
    retryLocalModelTurn
  } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';
  import { locale, t } from '$lib/i18n';
  import Icon from '$lib/components/common/Icon.svelte';
  import { claimSpeechRequest, speakLocalText, stopLocalText } from '$lib/bridge/voice';
  import ToolCallCard from './ToolCallCard.svelte';
  import CodeBlock from './CodeBlock.svelte';

  interface ContentBlock {
    type: 'text' | 'code';
    text?: string;
    code?: string;
    language?: string;
  }

  function parseMessageBlocks(body: string): ContentBlock[] {
    if (!body) return [];
    const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
    const blocks: ContentBlock[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = codeBlockRegex.exec(body)) !== null) {
      if (match.index > lastIndex) {
        const textSegment = body.slice(lastIndex, match.index);
        if (textSegment.trim() || textSegment.length > 0) {
          blocks.push({ type: 'text', text: textSegment });
        }
      }
      blocks.push({
        type: 'code',
        language: match[1] || 'text',
        code: match[2].trimEnd()
      });
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < body.length) {
      blocks.push({ type: 'text', text: body.slice(lastIndex) });
    }

    return blocks.length > 0 ? blocks : [{ type: 'text', text: body }];
  }
  import ApprovalCard from './ApprovalCard.svelte';

  /**
   * Prefill the composer from a prompt card.
   *
   * These cards previously had empty handlers, so clicking them did nothing.
   * Filling the draft keeps the user in control: nothing is sent until they
   * press send.
   */
  function insertPrompt(titleKey: string): void {
    const translate = $t;
    const text = `${translate(titleKey)} — ${translate(`${titleKey}_sub`)}`;
    setComposerDraft($composerDraft.trim() ? `${$composerDraft.trim()}\n${text}` : text);
  }

  function requestErrorReason(error: string): string {
    const bounded = String(error || '').trim().slice(0, 240);
    if (!bounded) return '';
    const safeCodes = [
      'path_outside_workspace',
      'workspace_digest_mismatch',
      'policy_denied',
      'approval_required',
      'ownership_missing',
      'model_not_ready',
      'runtime_unavailable',
      'gateway_unavailable',
      'tool_unsupported',
      'computer_use_blocked',
      'timeout'
    ];
    const tokens = Array.from(bounded.matchAll(/\b[a-z][a-z0-9_]{2,64}\b/gi), (match) => match[0].toLowerCase());
    const safeCode = safeCodes.find((code) => tokens.includes(code));
    if (safeCode) return `${$t('chat.request_failed_reason')}: ${safeCode}`;

    const safeClass = /(blocked|policy|allowlist|unsupported|invalid|outside[ _](the[ _])?workspace|approval|ownership|model|runtime|gateway|tool|computer use|not ready|permission|unavailable|timeout)/i.test(bounded)
      ? 'request_blocked_or_unavailable'
      : '';
    return safeClass ? `${$t('chat.request_failed_reason')}: ${safeClass}` : '';
  }

  $: visibleMessages = $chatMessages.filter((message) => message.conversationId === $selectedConversationId);
  $: showEmptyState = visibleMessages.length === 0;
  $: modelLoading = $acquisitionBusy || ['Validating', 'Starting', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '') ||
    ['Validating', 'Loading', 'Unloading'].includes($managedRuntimeStore.status?.model_state ?? '');
  $: emptyTitleKey = $managedModelReady
    ? 'chat.first_use_ready'
    : modelLoading
      ? 'chat.model_loading'
      : 'chat.model_unavailable';
  $: emptyDetailKey = $managedModelReady
    ? 'chat.first_use_detail'
    : modelLoading
      ? 'chat.model_loading_detail'
      : 'chat.model_unavailable_detail';

  let copiedMessageId: string | null = null;
  let copyTimeout: any = null;

  async function copyMessageBody(id: string, text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      copiedMessageId = id;
      if (copyTimeout) clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => {
        copiedMessageId = null;
      }, 2000);
    } catch {
      // ignore clipboard error
    }
  }

  function stateKey(state: string): string {
    return `chat.state_${state}`;
  }

  import { onDestroy } from 'svelte';
  import { voiceGender, voiceMode } from '$lib/stores/shellStore';

  onDestroy(() => {
    if (copyTimeout) {
      clearTimeout(copyTimeout);
      copyTimeout = null;
    }
    void stopLocalText();
  });
  $: {
    if ($voiceMode && $inferenceRequestStore.lifecycle === 'completed' && $inferenceRequestStore.requestId) {
      const requestId = $inferenceRequestStore.requestId;
      const lastMessage = $chatMessages.find(m => m.requestId === requestId && m.role === 'assistant');
      if (lastMessage && lastMessage.body && $locale === 'ru' && claimSpeechRequest(requestId)) {
        void speakLocalText(lastMessage.body, $voiceGender, $locale);
      }
    }
  }
</script>

<section class="message-list" aria-label={$t('chat.message_history')}>
  {#if showEmptyState}
      <EmptyState
        title={$t(emptyTitleKey)}
        detail={$t(emptyDetailKey)}
        busy={modelLoading}
        statusLabel={modelLoading ? $t('chat.model_loading_status') : $managedModelReady ? $t('chat.local_only_status') : undefined}
        actionLabel={!$managedModelReady && !modelLoading ? $t('chat.setup_local_ai') : undefined}
        actionTestId={!$managedModelReady && !modelLoading ? 'chat-setup-local-ai' : undefined}
        onAction={!$managedModelReady && !modelLoading ? () => openModelSetup('managed') : undefined}
      />
      {#if $managedModelReady}
        <div class="prompt-cards-section">
          <h3>{$t('chat.how_can_i_help')}</h3>
          <div class="cards-grid">
            <button type="button" class="prompt-card" onclick={() => insertPrompt('prompt.create_component')}>
              <span>{$t('prompt.create_component')}</span>
              <span class="prompt-sub">{$t('prompt.create_component_sub')}</span>
            </button>
            <button type="button" class="prompt-card" onclick={() => insertPrompt('prompt.explain_error')}>
              <span>{$t('prompt.explain_error')}</span>
              <span class="prompt-sub">{$t('prompt.explain_error_sub')}</span>
            </button>
            <button type="button" class="prompt-card" onclick={() => insertPrompt('prompt.write_tests')}>
              <span>{$t('prompt.write_tests')}</span>
              <span class="prompt-sub">{$t('prompt.write_tests_sub')}</span>
            </button>
            <button type="button" class="prompt-card" onclick={() => insertPrompt('prompt.optimize')}>
              <span>{$t('prompt.optimize')}</span>
              <span class="prompt-sub">{$t('prompt.optimize_sub')}</span>
            </button>
          </div>
        </div>
      {/if}
  {:else}
    {#each visibleMessages as message (message.id)}
      <article class="message {message.role}" aria-label={message.role === 'user' ? $t('chat.user_message') : $t('chat.model_response')}>
        <div class="avatar" aria-hidden="true">{message.role === 'user' ? 'U' : 'LC'}</div>
        <div class="bubble">
          <div class="bubble-meta">
            <span>{message.role === 'user' ? $t('chat.you') : $t('chat.model')}</span>
            {#if message.demo}
              <span class="demo-badge">{$t('chat.demo')}</span>
            {/if}
          </div>
          {#if message.role === 'user'}
            <p>{message.body}</p>
          {:else}
            {#each parseMessageBlocks(message.body) as block}
              {#if block.type === 'code'}
                <div class="code-wrapper">
                  <CodeBlock block={{ filename: block.language ?? 'code', language: block.language ?? 'text', code: block.code ?? '' }} />
                </div>
              {:else if block.text}
                <p>{block.text}</p>
              {/if}
            {/each}
            {#if message.reasoning && message.reasoning.length > 0}
              <details class="reasoning-block">
                <summary>{$t('reasoning.title')}</summary>
                <p class="reasoning-text">{message.reasoning}</p>
              </details>
            {/if}
          {/if}
          <div class="message-actions">
            <button
              type="button"
              class="msg-action-btn"
              title={copiedMessageId === message.id ? $t('chat.copied') : $t('chat.copy')}
              aria-label={$t('chat.copy')}
              onclick={() => copyMessageBody(message.id, message.body)}
            >
              <Icon name={copiedMessageId === message.id ? 'check' : 'copy'} size={14} />
              {#if copiedMessageId === message.id}
                <span class="copied-hint">{$t('chat.copied')}</span>
              {/if}
            </button>
          </div>
          {#if message.toolCalls}
            <div class="tool-calls-container">
              {#each message.toolCalls as tool}
                <ToolCallCard {tool} />
              {/each}
            </div>
          {/if}
            {#if message.role === 'assistant' && message.state && message.state !== 'completed'}
            <div class="request-result">
              <span class="request-state" data-state={message.state}>{$t(stateKey(message.state))}</span>
              {#if message.error && message.state === 'timed_out'}
                <span class="request-error-detail">{$t('chat.request_timed_out_detail')}</span>
              {:else if message.error && message.state === 'failed'}
                <span class="request-error-detail">{$t('chat.request_failed_detail')}</span>
                {#if requestErrorReason(message.error)}
                  <span class="request-error-cause">{requestErrorReason(message.error)}</span>
                {/if}
              {/if}
              {#if ['cancelled', 'timed_out', 'failed'].includes(message.state)}
                <button
                  type="button"
                  class="retry-button"
                  disabled={$inferenceBusy || !$managedModelReady}
                  onclick={() => void retryLocalModelTurn(message.requestId ?? '', $selectedConversationId)}
                >
                  {$t('chat.retry')}
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </article>
    {/each}
  {/if}
  
  <ApprovalCard />
</section>

<style>
  .message-list {
    min-width: 0;
    max-width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .prompt-cards-section {
    margin-top: 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }

  .prompt-cards-section h3 {
    font-size: 24px;
    font-weight: 600;
    color: var(--lc-text);
    margin: 0;
  }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    max-width: 600px;
    width: 100%;
  }

  .prompt-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 16px;
    background: var(--lc-panel);
    border: 1px solid var(--lc-line);
    border-radius: var(--radius-3);
    text-align: left;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .prompt-card:hover {
    background: var(--lc-panel-soft);
    border-color: var(--lc-accent);
  }

  .prompt-card span {
    font-size: 14px;
    font-weight: 500;
    color: var(--lc-text);
  }

  .prompt-card .prompt-sub {
    font-size: 13px;
    color: var(--lc-muted);
  }

  .message {
    min-width: 0;
    max-width: 100%;
    display: flex;
    justify-content: flex-start;
    animation: message-in 400ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  .message.user {
    justify-content: flex-end;
  }

  .avatar {
    display: none;
  }

  .bubble {
    min-width: 0;
    width: fit-content;
    max-width: 80%;
    border: 1px solid color-mix(in srgb, var(--lc-line) 84%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-panel-solid) 60%, transparent);
    padding: 10px 16px;
    font-size: 13.5px;
    line-height: 1.625;
  }

  .code-wrapper {
    margin: 8px 0;
    max-width: 100%;
    overflow-x: auto;
  }

  .reasoning-block {
    margin-top: 12px;
    padding: 8px 10px;
    border: 1px solid color-mix(in srgb, var(--lc-line) 72%, transparent);
    border-radius: var(--lc-radius-sm);
    background: color-mix(in srgb, var(--lc-panel-soft) 52%, transparent);
    color: var(--lc-muted);
  }

  .reasoning-block summary {
    color: var(--lc-faint);
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
    user-select: none;
  }

  .reasoning-block summary:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--lc-accent) 70%, transparent);
    outline-offset: 2px;
    border-radius: 4px;
  }

  .reasoning-text {
    margin-top: 8px;
    max-height: 260px;
    overflow: auto;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.55;
    white-space: pre-wrap;
  }

  .user .bubble {
    border-color: transparent;
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 500;
  }

  .runtime .bubble {
    border-color: var(--lc-line-strong);
  }

  .bubble-meta {
    display: none;
  }

  p {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .request-state {
    display: inline-block;
    margin-top: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    font-family: var(--lc-mono);
  }

  .user .request-state {
    color: currentColor;
  }

  .request-error-detail,
  .request-error-cause {
    display: block;
  }

  .request-error-cause {
    color: var(--lc-text-secondary);
    margin-top: 4px;
    overflow-wrap: anywhere;
  }

  .request-error-detail {
    max-width: min(620px, 100%);
    overflow-wrap: anywhere;
    color: var(--lc-danger);
    font-size: 12px;
    line-height: 1.45;
  }

  .request-result {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-2);
  }

  .request-result .request-state {
    margin-top: 0;
  }

  .retry-button {
    min-height: 30px;
    padding: 0 var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .retry-button:disabled {
    color: var(--lc-faint);
    cursor: not-allowed;
  }

  .message-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 4px;
    opacity: 0.7;
    transition: opacity 0.2s ease;
  }

  .bubble:hover .message-actions {
    opacity: 1;
  }

  .msg-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: none;
    color: inherit;
    opacity: 0.6;
    padding: 2px 6px;
    border-radius: var(--lc-radius-sm);
    cursor: pointer;
    font-size: 11px;
    transition: all 0.15s ease;
  }

  .msg-action-btn:hover {
    opacity: 1;
    background: color-mix(in srgb, currentColor 10%, transparent);
  }

  .copied-hint {
    font-size: 11px;
    font-weight: 500;
  }

  @keyframes message-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 680px) {
    .bubble {
      max-width: 94%;
    }
  }
</style>
