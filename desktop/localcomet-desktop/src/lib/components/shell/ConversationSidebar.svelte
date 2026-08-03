<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { conversationStore, createConversation, selectConversation } from '$lib/stores/conversationStore';
  import { sidebarExpanded } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  type Translate = (key: string) => string;

  function tTitle(value: string, translate: Translate): string {
    const v = translate('item.' + value);
    return v.startsWith('item.') ? value : v;
  }
</script>

<aside class="sidebar" class:sidebar-open={$sidebarExpanded} aria-label={$t('sidebar.label')}>
  <div class="sidebar-top">
    <button
      type="button"
      class="plain-button new-conversation-button"
      aria-label={$t('sidebar.new_conversation')}
      title={$t('sidebar.new_conversation')}
      onclick={() => createConversation()}
    >
      <Icon name="add" size={18} />
    </button>
    <button
      type="button"
      class="plain-button collapse-button"
      aria-label={$t('sidebar.collapse')}
      aria-expanded={$sidebarExpanded}
      onclick={() => sidebarExpanded.update((value) => !value)}
    >
      <Icon name={$sidebarExpanded ? 'collapse' : 'expand'} size={18} />
    </button>
  </div>

  <div class="conversation-groups">
    <section aria-label={$t('group.local_chats')}>
      <h2>{$t('group.local_chats')}</h2>
      {#if $conversationStore.conversations.length === 0}
        <p class="conversation-empty">{$t('conversation.empty')}</p>
      {:else}
        {#each $conversationStore.conversations as conversation (conversation.id)}
          <button
            type="button"
            class="conversation-button"
            class:selected={$conversationStore.activeId === conversation.id}
            aria-current={$conversationStore.activeId === conversation.id ? 'page' : undefined}
            onclick={() => selectConversation(conversation.id)}
          >
            <span>{tTitle(conversation.title, $t)}</span>
          </button>
        {/each}
      {/if}
    </section>
  </div>
</aside>

<style>
  .sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    display: flex;
    flex-direction: column;
    padding: 8px;
    overflow-y: auto;
    transition: transform var(--lc-transition-normal);
  }

  .sidebar-top {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 4px;
    min-height: 36px;
  }

  .collapse-button,
  .new-conversation-button {
    width: 34px;
    min-height: 34px;
    display: grid;
    place-items: center;
  }

  .conversation-empty {
    margin: 8px;
    color: var(--lc-faint);
    font-size: 12px;
  }

  h2 {
    margin: 12px 8px 6px;
    color: var(--lc-faint);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .conversation-button {
    width: 100%;
    min-height: 34px;
    display: block;
    text-align: left;
    padding: 6px 8px;
    color: var(--lc-muted);
    font-size: 12.5px;
    font-weight: 560;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .conversation-button.selected {
    background: var(--lc-accent-dim);
    border-color: transparent;
    color: var(--lc-accent);
  }

  @media (max-width: 920px) {
    .sidebar:not(.sidebar-open) {
      display: none;
    }

    .sidebar.sidebar-open {
      position: fixed;
      top: var(--shell-header-height);
      left: var(--rail-width);
      z-index: 35;
      display: flex;
      width: min(var(--sidebar-width), calc(100vw - var(--rail-width)));
      height: calc(100vh - var(--shell-header-height));
      box-shadow: var(--lc-shadow);
    }
  }
</style>
