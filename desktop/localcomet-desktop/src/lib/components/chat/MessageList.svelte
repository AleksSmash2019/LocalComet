<script lang="ts">
  import EmptyState from '$lib/components/common/EmptyState.svelte';
  import { chatMessages, openSettings, selectedConversationId } from '$lib/stores/shellStore';
  import {
    inferenceBusy,
    managedModelReady,
    managedRuntimeStore,
    retryLocalModelTurn
  } from '$lib/stores/modelGateway';
  import { acquisitionBusy } from '$lib/stores/artifactAcquisition';
  import { t } from '$lib/i18n';

  $: showEmptyState = $chatMessages.length === 0;
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

  function stateKey(state: string): string {
    return `chat.state_${state}`;
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
      onAction={!$managedModelReady && !modelLoading ? () => openSettings('models') : undefined}
    />
  {:else}
    {#each $chatMessages as message}
      <article class="message {message.role}" aria-label={message.role === 'user' ? $t('chat.user_message') : $t('chat.model_response')}>
        <div class="avatar" aria-hidden="true">{message.role === 'user' ? 'U' : 'LC'}</div>
        <div class="bubble">
          <div class="bubble-meta">
            <span>{message.role === 'user' ? $t('chat.you') : $t('chat.model')}</span>
            {#if message.demo}
              <span class="demo-badge">{$t('chat.demo')}</span>
            {/if}
          </div>
          <p>{message.body}</p>
          {#if message.role === 'assistant' && message.state && message.state !== 'completed'}
            <div class="request-result">
              <span class="request-state" data-state={message.state}>{$t(stateKey(message.state))}</span>
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
</section>

<style>
  .message-list {
    min-width: 0;
    max-width: 100%;
    display: grid;
    gap: 12px;
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
