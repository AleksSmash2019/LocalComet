<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import ModelManagerSection from '$lib/components/model/ModelManagerSection.svelte';
  import PermissionsSection from '$lib/components/shell/PermissionsSection.svelte';
  import ObservabilityRoom from '$lib/components/logs/ObservabilityRoom.svelte';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import {
    inspectorDrawerOpen,
    inspectorVisible,
    setDiagnosticsPanelOpen,
    settingsSection,
    setThemeMode,
    themeMode
  } from '$lib/stores/shellStore';
  import { availableLanguages, isLanguage, locale, setLocale, t } from '$lib/i18n';
  import type { ThemeMode } from '$lib/data/mockData';
  import {
    DESKTOP_BUILD_LABEL,
    DESKTOP_BUILD_STATUS,
    DESKTOP_SHELL_VERSION
  } from '$lib/version';
  import { filesCapabilityAvailable, initializeFilesCapability } from '$lib/stores/files';

  export let onClose: () => void = () => undefined;

  let closeButton: HTMLButtonElement;

  const sections = [
    { id: 'interface', labelKey: 'settings.tab_interface' },
    { id: 'models', labelKey: 'settings.tab_models' },
    { id: 'permissions', labelKey: 'settings.tab_permissions' },
    { id: 'observability', labelKey: 'settings.tab_observability' },
    { id: 'about', labelKey: 'settings.tab_about' }
  ] as const;

  const themes: ReadonlyArray<{ mode: ThemeMode; icon: string; labelKey: string }> = [
    { mode: 'system', icon: 'system', labelKey: 'settings.theme_system' },
    { mode: 'light', icon: 'sun', labelKey: 'settings.theme_light' },
    { mode: 'dark', icon: 'moon', labelKey: 'settings.theme_dark' }
  ];

  // Languages come from the shared registry, so adding a locale there makes it
  // appear here without touching this component.
  const languages = availableLanguages;

  function onLanguageChange(event: Event): void {
    const value = (event.currentTarget as HTMLSelectElement).value;
    if (isLanguage(value)) setLocale(value);
  }

  $: diagnosticsOpen = $inspectorVisible || $inspectorDrawerOpen;
  $: connectionLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');

  onMount(() => {
    closeButton?.focus();
    void initializeFilesCapability();
  });
</script>

<div
  id="settings-panel"
  class="settings-panel"
  role="dialog"
  aria-modal="false"
  aria-labelledby="settings-title"
>
  <header>
    <div>
      <span class="eyebrow">LocalComet</span>
      <h2 id="settings-title">{$t('settings.title')}</h2>
    </div>
    <button
      type="button"
      class="plain-button close-button"
      bind:this={closeButton}
      aria-label={$t('settings.close')}
      title={$t('settings.close')}
      onclick={onClose}
    >
      <Icon name="cancel" size={16} />
      <span>{$t('settings.close')}</span>
    </button>
  </header>

  <nav class="settings-tabs" aria-label={$t('settings.sections')}>
    {#each sections as item}
      <button
        type="button"
        class:active={$settingsSection === item.id}
        aria-current={$settingsSection === item.id ? 'page' : undefined}
        onclick={() => settingsSection.set(item.id)}
      >{$t(item.labelKey)}</button>
    {/each}
  </nav>

  <div class="settings-content">
    <div class:panel-hidden={$settingsSection !== 'interface'} aria-hidden={$settingsSection !== 'interface'}>
      <section aria-labelledby="settings-appearance">
      <h3 id="settings-appearance">{$t('settings.appearance')}</h3>
      <div class="choice-grid theme-grid" role="group" aria-label={$t('settings.theme')}>
        {#each themes as item}
          <button
            type="button"
            class:selected={$themeMode === item.mode}
            aria-label={$t(item.labelKey)}
            aria-pressed={$themeMode === item.mode}
            title={$t(item.labelKey)}
            onclick={() => setThemeMode(item.mode)}
          >
            <Icon name={item.icon} size={18} />
            <span>{$t(item.labelKey)}</span>
          </button>
        {/each}
      </div>
      </section>

      <section aria-labelledby="settings-language">
      <h3 id="settings-language">{$t('settings.language')}</h3>
      <div class="language-field">
        <select
          class="language-select"
          aria-label={$t('lang.select')}
          title={$t('lang.select')}
          value={$locale}
          onchange={onLanguageChange}
        >
          {#each languages as item}
            <option value={item.code} selected={$locale === item.code}>{item.endonym}</option>
          {/each}
        </select>
      </div>
      </section>

      <section aria-labelledby="settings-diagnostics">
      <h3 id="settings-diagnostics">{$t('settings.diagnostics')}</h3>
      <div class="diagnostics-setting">
        <div class="connection-state">
          <span>{$t('settings.connection_state')}</span>
          <output title={connectionLabel}>{connectionLabel}</output>
        </div>
        <button
          type="button"
          class="diagnostics-toggle"
          aria-pressed={diagnosticsOpen}
          aria-controls="diagnostics-panel"
          onclick={() => setDiagnosticsPanelOpen(!diagnosticsOpen)}
        >
          <Icon name="inspector" size={18} />
          <span>{$t(diagnosticsOpen ? 'settings.hide_diagnostics' : 'settings.show_diagnostics')}</span>
        </button>
      </div>
      </section>
    </div>

    <div class:panel-hidden={$settingsSection !== 'models'} aria-hidden={$settingsSection !== 'models'}>
      <ModelManagerSection />
    </div>
    <div class:panel-hidden={$settingsSection !== 'permissions'} aria-hidden={$settingsSection !== 'permissions'}>
      <PermissionsSection />
    </div>
    <div class:panel-hidden={$settingsSection !== 'observability'} aria-hidden={$settingsSection !== 'observability'}>
      <ObservabilityRoom />
    </div>

    <section class:panel-hidden={$settingsSection !== 'about'} aria-hidden={$settingsSection !== 'about'} aria-labelledby="settings-about">
      <h3 id="settings-about">{$t('settings.about')}</h3>
      <dl class="about-list">
        <div>
          <dt>{$t('settings.application')}</dt>
          <dd>LocalComet</dd>
        </div>
        <div>
          <dt>{$t('settings.version')}</dt>
          <dd>{DESKTOP_SHELL_VERSION}</dd>
        </div>
        <div>
          <dt>{$t('settings.build')}</dt>
          <dd>{DESKTOP_BUILD_LABEL}</dd>
        </div>
        <div>
          <dt>{$t('settings.build_status')}</dt>
          <dd>{DESKTOP_BUILD_STATUS}</dd>
        </div>
      </dl>
      <div class="capability-summary" aria-label={$t('settings.capabilities')}>
        <div>
          <h4>{$t('settings.available')}</h4>
          <ul>
            <li>{$t('capability.local_chat')}</li>
            <li>{$t('capability.local_model_inference')}</li>
            <li>{$t('capability.approved_model_setup')}</li>
            {#if $filesCapabilityAvailable}<li>{$t('capability.files')}</li>{/if}
          </ul>
        </div>
        <div>
          <h4>{$t('settings.unavailable')}</h4>
          <ul>
            <li>{$t('capability.internet')}</li>
            <li>{$t('capability.email')}</li>
            <li>{$t('capability.browser')}</li>
            {#if !$filesCapabilityAvailable}<li>{$t('capability.files')}</li>{/if}
            <li>{$t('capability.vault')}</li>
            <li>{$t('capability.computer_use')}</li>
            <li>{$t('capability.shell')}</li>
            <li>{$t('capability.external_tools')}</li>
          </ul>
        </div>
      </div>
      <p class="capability-note">{$t('settings.project_context_unavailable')}</p>
    </section>
  </div>
</div>

<style>
  .settings-panel {
    position: fixed;
    top: var(--shell-header-height);
    right: 0;
    bottom: 0;
    z-index: 50;
    width: min(820px, calc(100vw - var(--sidebar-width)));
    min-width: 0;
    overflow-y: auto;
    border-left: var(--border-thin);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
    color: var(--lc-text);
  }

  header {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-4);
  }

  .settings-tabs {
    position: sticky;
    top: 79px;
    z-index: 1;
    display: flex;
    gap: var(--lc-space-6);
    padding: 0 var(--lc-space-4);
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
  }

  .settings-tabs button {
    flex: 0 0 auto;
    min-height: 42px;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 0 var(--lc-space-3);
    background: transparent;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .settings-tabs button.active {
    border-bottom-color: var(--lc-accent);
    color: var(--lc-accent);
  }

  .eyebrow {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    margin-top: var(--lc-space-1);
    font-size: 19px;
  }

  h3 {
    margin-bottom: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .close-button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-1);
    min-height: 36px;
    padding: 0 var(--lc-space-2);
    color: var(--lc-muted);
  }

  .settings-content {
    display: grid;
    gap: var(--lc-space-5);
    padding: var(--lc-space-4);
  }

  .settings-content > div:not(.panel-hidden) {
    display: grid;
    gap: var(--lc-space-5);
  }

  .panel-hidden {
    display: none;
  }

  section {
    min-width: 0;
    border-bottom: var(--border-thin);
    padding-bottom: var(--lc-space-5);
  }

  section:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }

  .choice-grid {
    display: grid;
    gap: var(--lc-space-2);
  }

  .theme-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .language-field {
    display: grid;
  }

  .language-select {
    width: 100%;
    min-height: 44px;
    padding: 0 var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
  }

  .language-select:hover {
    border-color: var(--lc-line);
  }

  .language-select:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .choice-grid button,
  .diagnostics-toggle {
    min-width: 0;
    min-height: 44px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .choice-grid button {
    display: grid;
    place-items: center;
    gap: var(--lc-space-1);
    padding: var(--lc-space-2);
    text-align: center;
  }

  .choice-grid button:hover,
  .diagnostics-toggle:hover {
    border-color: var(--lc-line-strong);
    color: var(--lc-text);
  }

  .choice-grid button.selected,
  .diagnostics-toggle[aria-pressed='true'] {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .diagnostics-setting {
    display: grid;
    gap: var(--lc-space-3);
  }

  .connection-state {
    display: grid;
    gap: var(--lc-space-1);
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  .connection-state > span,
  dt {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 720;
  }

  output,
  dd {
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-size: 12px;
    font-weight: 760;
  }

  .capability-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-3);
  }

  .capability-summary > div {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  h4 {
    margin: 0 0 var(--lc-space-2);
    color: var(--lc-text);
    font-size: 12px;
  }

  ul {
    display: grid;
    gap: var(--lc-space-1);
    margin: 0;
    padding-left: 18px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  .capability-note {
    margin: var(--lc-space-3) 0 0;
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  .diagnostics-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    padding: 0 var(--lc-space-3);
  }

  .about-list {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .about-list div {
    display: grid;
    grid-template-columns: minmax(88px, 0.8fr) minmax(0, 1.2fr);
    gap: var(--lc-space-3);
    align-items: start;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  dd {
    margin: 0;
    text-align: right;
    font-family: var(--lc-mono);
  }

  @media (max-width: 520px) {
    .settings-panel {
      width: calc(100vw - var(--sidebar-width));
    }

    .theme-grid {
      grid-template-columns: 1fr;
    }

    .capability-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
