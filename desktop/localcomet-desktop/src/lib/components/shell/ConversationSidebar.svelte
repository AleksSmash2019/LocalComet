<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { conversationStore, createConversation, selectConversation } from '$lib/stores/conversationStore';
  import { activeWorkspace, closeSettings, openSettings, setActiveWorkspace, settingsPanelOpen, sidebarExpanded } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  export let controlPlaneLabel: string = '';
  export let controlPlaneTone: 'ready' | 'info' | 'danger' | 'disabled' | 'unknown' = 'unknown';

  type Translate = (key: string) => string;

  function tTitle(value: string, translate: Translate): string {
    const v = translate('item.' + value);
    return v.startsWith('item.') ? value : v;
  }

  function openChat(): void {
    closeSettings();
    setActiveWorkspace('chat');
  }
</script>

<aside class="sidebar" class:sidebar-open={$sidebarExpanded} aria-label={$t('sidebar.label')}>
  <div class="sidebar-top">
    <div class="sidebar-mark" title="LocalComet">
      <LocalCometLogo size={26} />
      <span class="sidebar-wordmark"><span>Local</span>Comet</span>
    </div>

    <div class="sidebar-nav">
      <button
        type="button"
        class="nav-button"
        aria-label={$t('nav.chat')}
        title={$t('nav.chat')}
        class:active={$activeWorkspace === 'chat' && !$settingsPanelOpen}
        onclick={openChat}
      >
        <span class="nav-dot"></span>
        {$t('nav.chat')}
      </button>
      <button
        type="button"
        class="nav-button"
        aria-label={$t('nav.hf_browser')}
        title={$t('nav.hf_browser')}
        class:active={$activeWorkspace === 'hf_browser' && !$settingsPanelOpen}
        onclick={() => setActiveWorkspace('hf_browser')}
      >
        <span class="nav-dot"></span>
        {$t('nav.hf_browser')}
      </button>
    </div>

    <button
      type="button"
      class="plain-button new-conversation-button"
      aria-label={$t('sidebar.new_conversation')}
      title={$t('sidebar.new_conversation')}
      onclick={() => createConversation()}
    >
      <div class="new-conv-left">
        <Icon name="add" size={16} />
        <span>{$t('sidebar.new_conversation')}</span>
      </div>
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

  <div class="sidebar-bottom">
    <button
      type="button"
      class="nav-button settings-button"
      aria-label={$t('nav.settings')}
      title={$t('nav.settings')}
      data-settings-trigger="true"
      class:active={$settingsPanelOpen}
      onclick={openSettings}
    >
      <Icon name="settings" size={16} />
      {$t('nav.settings')}
    </button>
  </div>
</aside>

<style>
  .sidebar {
    grid-row: 1 / 3;
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    display: flex;
    flex-direction: column;
    background: color-mix(in srgb, var(--lc-bg-elevated) 82%, transparent);
    backdrop-filter: blur(12px);
    border-right: var(--border-thin);
  }

  .sidebar-top {
    display: flex;
    flex-direction: column;
    padding: 16px;
    gap: 16px;
  }

  .sidebar-mark {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 8px;
    margin-bottom: 8px;
  }

  .sidebar-wordmark {
    min-width: 0;
    color: var(--lc-accent);
    font-family: Sora, Inter, "Segoe UI", system-ui, sans-serif;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: -0.025em;
    white-space: nowrap;
  }
  .sidebar-wordmark span { color: var(--lc-text); }

  .sidebar-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .nav-button {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    border-radius: var(--radius-2);
    color: var(--lc-muted);
    font-size: 14px;
    font-weight: 600;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
  }

  .nav-button:hover {
    background: var(--color-tool);
    color: var(--lc-text);
  }

  .nav-button.active {
    background: color-mix(in srgb, var(--lc-accent) 15%, transparent);
    color: var(--lc-text);
  }

  .nav-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--lc-accent);
    margin-left: 4px;
  }

  .new-conversation-button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: var(--radius-2);
    border: 1px solid var(--lc-accent);
    color: var(--lc-accent);
    background: transparent;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  
  .new-conv-left {
    display: flex;
    align-items: center;
    gap: 12px;
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

  .conversation-groups {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .sidebar-bottom {
    margin-top: auto;
    display: flex;
    flex-direction: column;
    padding: 16px;
    gap: 12px;
  }

  @media (max-width: 920px) {
    .sidebar:not(.sidebar-open) {
      display: none;
    }

    .sidebar.sidebar-open {
      position: fixed;
      top: var(--shell-header-height);
      left: var(--sidebar-width);
      z-index: 35;
      display: block;
      width: calc(100vw - var(--sidebar-width));
      height: calc(100vh - var(--shell-header-height));
      box-shadow: var(--lc-shadow);
    }
  }
</style>
