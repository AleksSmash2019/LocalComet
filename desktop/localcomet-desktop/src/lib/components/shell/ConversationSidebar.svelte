<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import { conversationStore, createConversation, selectConversation } from '$lib/stores/conversationStore';
  import { activeWorkspace, closeSettings, openSettings, setActiveWorkspace, setComposerDraft, settingsPanelOpen, sidebarExpanded } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  type Translate = (key: string) => string;

  function tTitle(value: string, translate: Translate): string {
    const v = translate('item.' + value);
    return v.startsWith('item.') ? value : v;
  }

  function startNewConversation(): void {
    closeSettings();
    setActiveWorkspace('chat');
    createConversation();
    setComposerDraft('');
  }

  function openConversation(id: string): void {
    closeSettings();
    setActiveWorkspace('chat');
    selectConversation(id);
    setComposerDraft('');
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
        <Icon name="chat" size={16} />
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
        <Icon name="hf" size={16} />
        {$t('nav.hf_browser')}
      </button>
      <button
        type="button"
        class="nav-button"
        aria-label={$t('modelfit.title')}
        title={$t('modelfit.title')}
        class:active={$activeWorkspace === 'modelfit' && !$settingsPanelOpen}
        onclick={() => setActiveWorkspace('modelfit')}
      >
        <Icon name="hardware" size={16} />
        {$t('modelfit.title')}
      </button>
    </div>

    <button
      type="button"
      class="plain-button new-conversation-button"
      aria-label={$t('sidebar.new_conversation')}
      title={$t('sidebar.new_conversation')}
      onclick={startNewConversation}
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
            onclick={() => openConversation(conversation.id)}
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
    background: color-mix(in srgb, var(--lc-bg-elevated) 60%, transparent);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-right: var(--border-thin);
    z-index: 20;
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
    gap: 6px;
  }

  .nav-button {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: var(--radius-3);
    color: var(--lc-muted);
    font-size: 14px;
    font-weight: 600;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
  }

  .nav-button:hover {
    background: color-mix(in srgb, var(--lc-text) 8%, transparent);
    color: var(--lc-text);
  }

  .nav-button.active {
    background: linear-gradient(90deg, var(--lc-accent-dim) 0%, transparent 100%);
    color: var(--lc-text);
    box-shadow: inset 3px 0 0 var(--lc-accent);
  }

  .new-conversation-button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-radius: var(--radius-3);
    border: 1px solid color-mix(in srgb, var(--lc-accent) 30%, transparent);
    color: var(--lc-accent);
    background: color-mix(in srgb, var(--lc-accent) 5%, transparent);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  
  .new-conversation-button:hover {
    background: color-mix(in srgb, var(--lc-accent) 12%, transparent);
    border-color: color-mix(in srgb, var(--lc-accent) 50%, transparent);
    transform: translateY(-2px);
    box-shadow: 0 6px 16px color-mix(in srgb, var(--lc-accent) 15%, transparent);
  }

  .new-conv-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .conversation-empty {
    margin: 16px 8px;
    padding: 12px;
    border-radius: var(--radius-2);
    background: color-mix(in srgb, var(--lc-text) 2%, transparent);
    color: var(--lc-muted);
    font-size: 12.5px;
    text-align: center;
    border: 1px dashed color-mix(in srgb, var(--lc-line) 50%, transparent);
  }

  h2 {
    margin: 20px 8px 8px;
    color: var(--lc-faint);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
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
