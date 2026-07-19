<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import { t } from '$lib/i18n';
  import {
    activeWorkspace,
    setActiveWorkspace,
    type WorkspaceMode
  } from '$lib/stores/shellStore';

  type NavigationItem = {
    icon: string;
    key: string;
    enabled: boolean;
    workspace?: WorkspaceMode;
  };

  const primaryItems: readonly NavigationItem[] = [
    { icon: 'chat', key: 'nav.chat', enabled: true, workspace: 'chat' },
    { icon: 'tasks', key: 'nav.tasks', enabled: false },
    { icon: 'inspector', key: 'nav.diagnostics', enabled: true, workspace: 'chat' },
    { icon: 'audit', key: 'nav.review_center', enabled: true, workspace: 'review' },
    { icon: 'settings', key: 'nav.settings', enabled: false }
  ];

  let selectedIndex = 0;

  $: if ($activeWorkspace === 'review') {
    selectedIndex = 3;
  } else if ($activeWorkspace === 'chat' && selectedIndex === 3) {
    selectedIndex = 0;
  }

  function activate(item: NavigationItem, index: number): void {
    if (!item.enabled) return;
    selectedIndex = index;
    if (item.workspace) setActiveWorkspace(item.workspace);
  }
</script>

<nav class="rail" aria-label={$t('nav.main')}>
  <div class="rail-mark" title="LocalComet">
    <LocalCometLogo size={34} />
  </div>
  <div class="rail-group" role="list">
    {#each primaryItems as item, i}
      {@const label = $t(item.key)}
      <button
        type="button"
        class="rail-button"
        aria-label={item.enabled ? label : `${label} — ${$t('nav.later')}`}
        aria-current={selectedIndex === i ? 'page' : undefined}
        aria-disabled={!item.enabled}
        title={item.enabled ? label : `${label} — ${$t('nav.later')}`}
        onclick={() => activate(item, i)}
      >
        <Icon name={item.icon} />
        {#if !item.enabled}
          <span class="rail-disabled" aria-hidden="true"></span>
        {/if}
      </button>
    {/each}
  </div>
</nav>

<style>
  .rail {
    width: var(--rail-width);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--lc-space-3) 2px;
    gap: var(--lc-space-3);
  }

  .rail-mark {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
  }

  .rail-group {
    display: grid;
    gap: var(--lc-space-2);
  }

  .rail-button {
    position: relative;
    width: 44px;
    height: 44px;
    display: grid;
    place-items: center;
    color: var(--lc-muted);
  }

  .rail-button[aria-current='page'] {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
    border-color: var(--lc-line-strong);
  }

  .rail-button[aria-disabled='true'] {
    color: var(--lc-faint);
  }

  .rail-disabled {
    position: absolute;
    right: 8px;
    bottom: 8px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--lc-faint);
  }
</style>
