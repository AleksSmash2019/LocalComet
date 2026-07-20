<script lang="ts">
  import EmptyState from '$lib/components/common/EmptyState.svelte';
  import { chatMessages, openModelSetup, selectedConversationId } from '$lib/stores/shellStore';
  import {
    approvedManagedModelInstalled,
    inferenceBusy,
    managedModelReady,
    managedRuntimeStore,
    retryLocalModelTurn
  } from '$lib/stores/modelGateway';
  import { t } from '$lib/i18n';

  $: showEmptyState = $chatMessages.length === 0;
  $: modelLoading = ['Validating', 'Starting', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '') ||
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
      actionLabel={!$managedModelReady && !modelLoading ? $t('chat.connect_model') : undefined}
      onAction={!$managedModelReady && !modelLoading ? () => openModelSetup($approvedManagedModelInstalled ? 'managed' : 'external') : undefined}
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
    gap: var(--lc-space-4);
  }

  .message {
    min-width: 0;
    max-width: 100%;
    display: grid;
    grid-template-columns: 38px minmax(0, 1fr);
    gap: var(--lc-space-3);
  }

  .message.user {
    max-width: 760px;
    margin-left: auto;
  }

  .avatar {
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    border: var(--border-thin);
    border-radius: 50%;
    background: var(--lc-panel-solid);
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
    font-weight: 800;
  }

  .bubble {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-4);
    line-height: 1.58;
  }

  .user .bubble {
    background: var(--lc-accent-dim);
    border-color: var(--lc-line-strong);
  }

  .runtime .bubble {
    border-color: var(--lc-line-strong);
  }

  .bubble-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--lc-space-2);
    margin-bottom: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
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

  @media (max-width: 680px) {
    .message {
      grid-template-columns: 1fr;
    }

    .avatar {
      display: none;
    }
  }
</style>
