<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import ThemeToggle from '$lib/components/common/ThemeToggle.svelte';
  import LanguageSwitcher from '$lib/components/common/LanguageSwitcher.svelte';
  import { conversationGroups, pinnedProject, projectLabels } from '$lib/data/mockData';
  import { selectedConversationId, setSelectedConversation, sidebarExpanded } from '$lib/stores/shellStore';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { t } from '$lib/i18n';

  $: sessionState = $controlPlaneStore.currentSession?.state ?? 'Unknown';
  $: sessionTone = $controlPlaneStore.currentSession ? 'ready' : 'unknown';

  function tGroup(label: string): string {
    const v = $t('group.' + label);
    return v.startsWith('group.') ? label : v;
  }

  function tItem(value: string): string {
    const v = $t('item.' + value);
    return v.startsWith('item.') ? value : v;
  }

  function tProjectLabel(label: string): string {
    const key = label === 'Frontend' ? 'project.label_frontend' : label === 'Русский UX' ? 'project.label_russian_ux' : label;
    const v = $t(key);
    return v.startsWith('project.') ? label : v;
  }
</script>

<aside class="sidebar" class:sidebar-open={$sidebarExpanded} aria-label={$t('sidebar.label')}>
  <div class="sidebar-top">
    <button type="button" class="new-thread" disabled title={$t('sidebar.new_thread_title')}>
      <Icon name="add" size={18} />
      <span>{$t('sidebar.new_thread')}</span>
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

  <section class="pinned" aria-label={$t('sidebar.pinned_label')}>
    <span class="eyebrow">{$t('sidebar.pinned')}</span>
    <strong>{pinnedProject.title}</strong>
    <span>{$t('project.detail')}</span>
    <div class="labels" aria-label={$t('sidebar.project_labels')}>
      {#each projectLabels as label}
        <span>{tProjectLabel(label)}</span>
      {/each}
    </div>
  </section>

  <div class="conversation-groups">
    {#each conversationGroups as group}
      <section aria-label={tGroup(group.label)}>
        <h2>{tGroup(group.label)}</h2>
        {#each group.items as item}
          <button
            type="button"
            class="conversation-button"
            class:selected={$selectedConversationId === item.id}
            aria-current={$selectedConversationId === item.id ? 'page' : undefined}
            onclick={() => setSelectedConversation(item.id)}
          >
            <span>{tItem(item.title)}</span>
            <small>{tItem(item.meta)}</small>
          </button>
        {/each}
      </section>
    {/each}
  </div>

  <footer>
    <LanguageSwitcher />
    <ThemeToggle />
  </footer>
</aside>

<style>
  .sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    display: flex;
    flex-direction: column;
    padding: var(--lc-space-4);
    overflow-y: auto;
    transition: transform var(--lc-transition-normal);
  }

  .sidebar-top {
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
  }

  .new-thread {
    flex: 1;
    min-width: 0;
    min-height: 40px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-muted);
    padding: 0 var(--lc-space-3);
    font-weight: 780;
  }

  .collapse-button {
    width: 40px;
    display: grid;
    place-items: center;
  }

  .pinned {
    margin: var(--lc-space-4) 0;
    padding: var(--lc-space-4);
    display: grid;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-solid);
  }

  .eyebrow,
  .pinned span,
  small {
    color: var(--lc-muted);
    font-size: 12px;
  }

  strong {
    overflow-wrap: anywhere;
  }

  .labels {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .labels span {
    border: var(--border-thin);
    border-radius: 999px;
    padding: var(--lc-space-1) var(--lc-space-2);
    background: var(--lc-panel-soft);
  }

  h2 {
    margin: var(--lc-space-5) 0 var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    text-transform: uppercase;
  }

  .conversation-button {
    width: 100%;
    min-height: 54px;
    display: grid;
    gap: var(--lc-space-1);
    text-align: left;
    padding: var(--lc-space-2) var(--lc-space-3);
    color: var(--lc-text);
  }

  .conversation-button.selected {
    background: var(--lc-accent-dim);
    border-color: var(--lc-line-strong);
  }

  footer {
    margin-top: auto;
    padding-top: var(--lc-space-4);
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    align-items: center;
  }

  @media (max-width: 920px) {
    .sidebar:not(.sidebar-open) {
      display: none;
    }

    .sidebar.sidebar-open {
      position: fixed;
      top: 38px;
      left: var(--rail-width);
      z-index: 35;
      display: flex;
      width: min(var(--sidebar-width), calc(100vw - var(--rail-width)));
      height: calc(100vh - 38px);
      box-shadow: var(--lc-shadow);
    }
  }
</style>
