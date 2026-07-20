<script lang="ts">
  import EmptyState from '$lib/components/common/EmptyState.svelte';
  import { chatMessages, openModelSetup } from '$lib/stores/shellStore';
  import { approvedManagedModelInstalled, managedModelReady } from '$lib/stores/modelGateway';
  import { t } from '$lib/i18n';

  $: showEmptyState = !$managedModelReady && $chatMessages.length === 0;
</script>

<section class="message-list" aria-label={$t('chat.message_history')}>
  {#if showEmptyState}
    <EmptyState
      title={$t('chat.model_not_connected')}
      detail={$t('chat.model_not_connected_detail')}
      actionLabel={$t('chat.connect_model')}
      onAction={() => openModelSetup($approvedManagedModelInstalled ? 'managed' : 'external')}
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
            <span class="request-state" data-state={message.state}>{message.error ?? message.state}</span>
          {/if}
        </div>
      </article>
    {/each}
  {/if}
</section>

<style>
  .message-list {
    display: grid;
    gap: var(--lc-space-4);
  }

  .message {
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
    overflow-wrap: anywhere;
  }

  .request-state {
    display: inline-block;
    margin-top: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    font-family: var(--lc-mono);
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
