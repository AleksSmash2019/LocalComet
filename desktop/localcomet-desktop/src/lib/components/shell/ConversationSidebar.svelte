<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { conversationGroups } from '$lib/data/mockData';
  import { selectedConversationId, setSelectedConversation, sidebarExpanded } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  const hiddenConversationGroupLabels = new Set(['reserved', 'disabled']);
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
    padding: 8px;
    overflow-y: auto;
    transition: transform var(--lc-transition-normal);
  }

  .sidebar-top {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    min-height: 36px;
  }

  .collapse-button {
    width: 34px;
    min-height: 34px;
    display: grid;
    place-items: center;
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
