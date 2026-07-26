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

  function openSetup(): void {
    closeSettings();
    setActiveWorkspace('setup');
  }

</script>

<nav class="rail" aria-label={$t('nav.main')}>
  <div class="rail-mark" title="LocalComet">
    <LocalCometLogo size={26} />
    <span class="rail-wordmark"><span>Local</span>Comet</span>
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
      <span class="rail-label">{$t('nav.chat')}</span>
    </button>
    <button
      type="button"
      class="rail-button"
      aria-label={$t('nav.setup')}
      aria-current={$activeWorkspace === 'setup' && !$settingsPanelOpen ? 'page' : undefined}
      title={$t('nav.setup')}
      onclick={openSetup}
    >
      <Icon name="spark" />
      <span class="rail-label">{$t('nav.setup')}</span>
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
      <span class="rail-label">{$t('nav.settings')}</span>
    </button>
  </div>
</nav>

<style>
  .rail {
    grid-column: 1;
    grid-row: 1 / 3;
    width: var(--rail-width);
    min-width: var(--rail-width);
    display: flex;
    flex-direction: column;
    border-right: var(--border-thin);
    background: color-mix(in srgb, var(--lc-bg-elevated) 82%, transparent);
    backdrop-filter: blur(12px);
  }

  .rail-mark {
    height: var(--shell-header-height);
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: var(--border-thin);
    padding: 0 20px;
  }

  .rail-wordmark {
    min-width: 0;
    color: var(--lc-accent);
    font-family: Sora, Inter, "Segoe UI", system-ui, sans-serif;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: -0.025em;
    white-space: nowrap;
  }

  .rail-wordmark span {
    color: var(--lc-text);
  }

  .rail-group {
    display: grid;
    gap: 2px;
    padding: 8px 12px;
  }

  .rail-bottom {
    margin-top: auto;
    border-top: var(--border-thin);
  }

  .rail-button {
    position: relative;
    width: 100%;
    min-height: 36px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 12px;
    color: var(--lc-muted);
    font-size: 13.5px;
    font-weight: 600;
    text-align: left;
  }

  .rail-button[aria-current='page'] {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
    border-color: transparent;
  }

  .rail-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  @media (max-width: 1279px) {
    .rail-mark {
      justify-content: center;
      padding: 0;
    }

    .rail-wordmark,
    .rail-label {
      display: none;
    }

    .rail-group {
      padding: 8px 4px;
    }

    .rail-button {
      justify-content: center;
      min-height: 44px;
      padding: 0;
    }
  }
</style>
