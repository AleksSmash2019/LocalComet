<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { conversationGroups, pinnedProject } from '$lib/data/mockData';
  import { selectedConversationId, setSelectedConversation, sidebarExpanded } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  const hiddenConversationGroupLabels = new Set(['Зарезервировано', 'Отключено']);
  const visibleConversationGroups = conversationGroups
    .filter((group) => !hiddenConversationGroupLabels.has(group.label))
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.id !== 'cancellation-demo')
    }))
    .filter((group) => group.items.length > 0);

  type Translate = (key: string) => string;

  function tGroup(label: string, translate: Translate): string {
    const v = translate('group.' + label);
    return v.startsWith('group.') ? label : v;
  }

  function tItem(value: string, translate: Translate): string {
    const v = translate('item.' + value);
    return v.startsWith('item.') ? value : v;
  }

</script>

<aside class="sidebar" class:sidebar-open={$sidebarExpanded} aria-label={$t('sidebar.label')}>
  <div class="sidebar-top">
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
    <strong>{pinnedProject.title}</strong>
    <span>{$t('project.detail')}</span>
  </section>

  <div class="conversation-groups">
    {#each visibleConversationGroups as group}
      <section aria-label={tGroup(group.label, $t)}>
        <h2>{tGroup(group.label, $t)}</h2>
        {#each group.items as item}
          <button
            type="button"
            class="conversation-button"
            class:selected={$selectedConversationId === item.id}
            aria-current={$selectedConversationId === item.id ? 'page' : undefined}
            onclick={() => setSelectedConversation(item.id)}
          >
            <span>{tItem(item.title, $t)}</span>
            <small>{tItem(item.meta, $t)}</small>
          </button>
        {/each}
      </section>
    {/each}
  </div>
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
    justify-content: flex-end;
    gap: var(--lc-space-2);
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

  .pinned span,
  small {
    color: var(--lc-muted);
    font-size: 12px;
  }

  strong {
    overflow-wrap: anywhere;
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
