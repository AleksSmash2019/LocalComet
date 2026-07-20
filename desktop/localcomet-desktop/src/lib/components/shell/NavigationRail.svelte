<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import { t } from '$lib/i18n';
  import {
    activeWorkspace,
    closeSettings,
    openSettings,
    setActiveWorkspace,
    settingsPanelOpen
  } from '$lib/stores/shellStore';

  function openChat(): void {
    closeSettings();
    setActiveWorkspace('chat');
  }
</script>

<nav class="rail" aria-label={$t('nav.main')}>
  <div class="rail-mark" title="LocalComet">
    <LocalCometLogo size={34} />
  </div>
  <div class="rail-group">
    <button
      type="button"
      class="rail-button"
      aria-label={$t('nav.chat')}
      aria-current={$activeWorkspace === 'chat' && !$settingsPanelOpen ? 'page' : undefined}
      title={$t('nav.chat')}
      onclick={openChat}
    >
      <Icon name="chat" />
    </button>
  </div>
  <div class="rail-group rail-bottom">
    <button
      type="button"
      class="rail-button"
      aria-label={$t('nav.settings')}
      aria-current={$settingsPanelOpen ? 'page' : undefined}
      title={$t('nav.settings')}
      data-settings-trigger="true"
      onclick={openSettings}
    >
      <Icon name="settings" />
    </button>
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

  .rail-bottom {
    margin-top: auto;
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

  .rail-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }
</style>
