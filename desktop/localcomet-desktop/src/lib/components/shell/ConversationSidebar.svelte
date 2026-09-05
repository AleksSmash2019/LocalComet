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

    <button
      type="button"
      class="new-conversation-button"
      aria-label={$t('sidebar.new_conversation')}
      title={$t('sidebar.new_conversation')}
      onclick={startNewConversation}
    >
      <span class="new-conv-plus"><Icon name="add" size={15} /></span>
      <span class="new-conv-label">{$t('sidebar.new_conversation')}</span>
    </button>

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
        <span>{$t('nav.chat')}</span>
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
        <span>{$t('nav.hf_browser')}</span>
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
        <span>{$t('modelfit.title')}</span>
      </button>
    </div>

    <button
      type="button"
      class="plain-button collapse-button"
      aria-label={$t('sidebar.collapse')}
      aria-expanded={$sidebarExpanded}
      onclick={() => sidebarExpanded.update((value) => !value)}
    >
      <Icon name={$sidebarExpanded ? 'collapse' : 'expand'} size={16} />
    </button>
  </div>

  <div class="conversation-groups">
    <section aria-label={$t('group.local_chats')}>
      <h2><span class="h2-rule"></span>{$t('group.local_chats')}</h2>
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
            <span class="conversation-dot" aria-hidden="true"></span>
            <span class="conversation-title">{tTitle(conversation.title, $t)}</span>
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
    grid-row: 2;
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
    gap: 2px;
  }

  .nav-button {
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 12px;
    border-radius: 10px;
    color: var(--lc-muted);
    font-size: 13.5px;
    font-weight: 570;
    letter-spacing: 0.01em;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.18s ease, color 0.18s ease;
  }

  .nav-button :global(svg) {
    opacity: 0.85;
    transition: opacity 0.18s ease, transform 0.18s ease;
  }

  .nav-button:hover {
    background: color-mix(in srgb, var(--lc-text) 7%, transparent);
    color: var(--lc-text);
  }

  .nav-button:hover :global(svg) {
    opacity: 1;
  }

  .nav-button.active {
    background:
      linear-gradient(90deg, color-mix(in srgb, var(--lc-accent) 14%, transparent) 0%, transparent 90%);
    color: var(--lc-text);
    font-weight: 640;
  }

  .nav-button.active :global(svg) {
    opacity: 1;
    color: var(--lc-accent);
    transform: scale(1.05);
  }

  .nav-button.active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 8px;
    bottom: 8px;
    width: 3px;
    border-radius: 3px;
    background: linear-gradient(180deg, var(--lc-accent-strong), var(--lc-accent));
    box-shadow: 0 0 10px color-mix(in srgb, var(--lc-accent) 45%, transparent);
  }

  .new-conversation-button {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 12px;
    border: 1px solid color-mix(in srgb, var(--lc-accent) 34%, transparent);
    color: var(--lc-accent);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--lc-accent) 12%, transparent) 0%, color-mix(in srgb, var(--lc-accent) 5%, transparent) 100%);
    font-size: 13.5px;
    font-weight: 620;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s cubic-bezier(0.34, 1.4, 0.64, 1);
  }

  .new-conv-plus {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: 7px;
    background: color-mix(in srgb, var(--lc-accent) 16%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lc-accent) 26%, transparent);
  }

  .new-conversation-button:hover {
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--lc-accent) 18%, transparent) 0%, color-mix(in srgb, var(--lc-accent) 8%, transparent) 100%);
    border-color: color-mix(in srgb, var(--lc-accent) 55%, transparent);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px color-mix(in srgb, var(--lc-accent) 18%, transparent);
  }

  .new-conversation-button:active {
    transform: translateY(0);
  }

  .new-conv-label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .conversation-empty {
    margin: 16px 8px;
    padding: 12px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--lc-text) 2%, transparent);
    color: var(--lc-muted);
    font-size: 12.5px;
    text-align: center;
    border: 1px dashed color-mix(in srgb, var(--lc-line) 50%, transparent);
  }

  h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 20px 8px 8px;
    color: var(--lc-faint);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .h2-rule {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, color-mix(in srgb, var(--lc-line) 55%, transparent), transparent);
  }

  .conversation-button {
    position: relative;
    width: 100%;
    min-height: 32px;
    display: flex;
    align-items: center;
    gap: 9px;
    text-align: left;
    padding: 6px 10px;
    border-radius: 8px;
    color: var(--lc-muted);
    font-size: 12.5px;
    font-weight: 540;
    cursor: pointer;
    transition: background 0.16s ease, color 0.16s ease;
  }

  .conversation-dot {
    flex: none;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--lc-muted) 55%, transparent);
    transition: background 0.16s ease, box-shadow 0.16s ease;
  }

  .conversation-title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .conversation-button:hover {
    background: color-mix(in srgb, var(--lc-text) 6%, transparent);
    color: var(--lc-text);
  }

  .conversation-button.selected {
    background:
      linear-gradient(90deg, color-mix(in srgb, var(--lc-accent) 12%, transparent) 0%, transparent 95%);
    color: var(--lc-text);
    font-weight: 620;
  }

  .conversation-button.selected .conversation-dot {
    background: var(--lc-accent);
    box-shadow: 0 0 8px color-mix(in srgb, var(--lc-accent) 55%, transparent);
  }

  .collapse-button {
    align-self: center;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    margin-top: -4px;
    border-radius: 9px;
    color: var(--lc-faint);
    cursor: pointer;
    background: transparent;
    border: none;
    transition: background 0.18s ease, color 0.18s ease;
  }

  .collapse-button:hover {
    background: color-mix(in srgb, var(--lc-text) 7%, transparent);
    color: var(--lc-text);
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
      top: calc(var(--app-menubar-height) + var(--shell-header-height));
      left: var(--sidebar-width);
      z-index: 35;
      display: block;
      width: calc(100vw - var(--sidebar-width));
      height: calc(100vh - var(--app-menubar-height) - var(--shell-header-height));
      box-shadow: var(--lc-shadow);
    }
  }
</style>
