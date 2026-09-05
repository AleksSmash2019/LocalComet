<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import ModelManagerSection from '$lib/components/model/ModelManagerSection.svelte';
  import SkillsManagerSection from '$lib/components/model/SkillsManagerSection.svelte';
  import PermissionsSection from '$lib/components/shell/PermissionsSection.svelte';
  import CheckpointPanel from '$lib/components/shell/CheckpointPanel.svelte';
  import CodingPanel from '$lib/components/shell/CodingPanel.svelte';
  import ObservabilityRoom from '$lib/components/logs/ObservabilityRoom.svelte';
  import { controlPlaneBridgeState } from '$lib/stores/controlPlane';
  import {
    inspectorDrawerOpen,
    inspectorVisible,
    setAccentColor,
    setDiagnosticsPanelOpen,
    settingsSection,
    setThemeMode,
    themeMode,
    setVoiceGender,
    voiceGender,
    accentColor
  } from '$lib/stores/shellStore';
  import { ACCENT_PRESETS } from '$lib/stores/uiPreferences';
  import { availableLanguages, isLanguage, locale, setLocale, t } from '$lib/i18n';
  import type { ThemeMode } from '$lib/data/mockData';
  import type { VoiceProfile } from '$lib/stores/uiPreferences';
  import {
    DESKTOP_BUILD_LABEL,
    DESKTOP_BUILD_STATUS,
    DESKTOP_SHELL_VERSION
  } from '$lib/version';
  import { filesCapabilityAvailable, initializeFilesCapability } from '$lib/stores/files';
  import { chooseWorkspace, restoreWorkspace, workspaceStore } from '$lib/stores/workspace';
  import { speakLocalText, stopLocalText } from '$lib/bridge/voice';

  export let onClose: () => void = () => undefined;

  let closeButton: HTMLButtonElement;

  const sections = [
    { id: 'interface', icon: 'settings', labelKey: 'settings.tab_interface' },
    { id: 'models', icon: 'model', labelKey: 'settings.tab_models' },
    { id: 'skills', icon: 'tool', labelKey: 'skills.title' },
    { id: 'permissions', icon: 'shield', labelKey: 'settings.tab_permissions' },
    { id: 'checkpoints', icon: 'audit', labelKey: 'checkpoints.title' },
    { id: 'coding', icon: 'terminal', labelKey: 'coding.title' },
    { id: 'observability', icon: 'diag', labelKey: 'settings.tab_observability' },
    { id: 'about', icon: 'inspector', labelKey: 'settings.tab_about' }
  ] as const;

  const themes: ReadonlyArray<{ mode: ThemeMode; icon: string; labelKey: string }> = [
    { mode: 'system', icon: 'system', labelKey: 'settings.theme_system' },
    { mode: 'light', icon: 'sun', labelKey: 'settings.theme_light' },
    { mode: 'dark', icon: 'moon', labelKey: 'settings.theme_dark' }
  ];

  const ttsVoices: ReadonlyArray<{ gender: VoiceProfile; labelKey: string; descriptionKey: string }> = [
    { gender: 'female', labelKey: 'settings.voice_female', descriptionKey: 'settings.voice_female_description' },
    { gender: 'male', labelKey: 'settings.voice_male', descriptionKey: 'settings.voice_male_description' },
    { gender: 'dmitri', labelKey: 'settings.voice_dmitri', descriptionKey: 'settings.voice_dmitri_description' },
    { gender: 'denis', labelKey: 'settings.voice_denis', descriptionKey: 'settings.voice_denis_description' }
  ];

  // Languages come from the shared registry, so adding a locale there makes it
  // appear here without touching this component.
  const languages = availableLanguages;

  function onLanguageChange(event: Event): void {
    const value = (event.currentTarget as HTMLSelectElement).value;
    if (isLanguage(value)) setLocale(value);
  }

  function selectVoiceGender(gender: VoiceProfile): void {
    if ($voiceGender === gender) return;
    setVoiceGender(gender);
    void stopLocalText();
  }

  function previewVoiceGender(gender: VoiceProfile): void {
    setVoiceGender(gender);
    void stopLocalText().then(() => speakLocalText($t('settings.voice_preview_text'), gender, $locale));
  }

  const isAccentHex = (value: string): boolean => /^#[0-9a-fA-F]{6}$/.test(value);

  function applyAccentPreset(value: string): void {
    setAccentColor(value.toLowerCase());
  }

  function onCustomAccentInput(event: Event): void {
    const value = (event.currentTarget as HTMLInputElement).value;
    if (isAccentHex(value)) setAccentColor(value.toLowerCase());
  }

  function resetAccent(): void {
    setAccentColor(null);
  }

  $: diagnosticsOpen = $inspectorVisible || $inspectorDrawerOpen;
  $: connectionLabel =
    $controlPlaneBridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneBridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneBridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneBridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');

  onMount(() => {
    closeButton?.focus();
    void initializeFilesCapability();
    void restoreWorkspace();
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
      <Icon name="cancel" size={15} />
      <span>{$t('settings.close')}</span>
    </button>
  </header>

  <nav class="settings-tabs" aria-label={$t('settings.sections')}>
    {#each sections as item}
      <button
        type="button"
        class:active={$settingsSection === item.id}
        aria-current={$settingsSection === item.id ? 'page' : undefined}
        aria-label={$t(item.labelKey)}
        title={$t(item.labelKey)}
        onclick={() => settingsSection.set(item.id)}
      >
        <Icon name={item.icon} size={15} />
        <span>{$t(item.labelKey)}</span>
      </button>
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

      <section aria-labelledby="settings-accent">
        <h3 id="settings-accent">{$t('settings.accent_title')}</h3>
        <p class="workspace-description">{$t('settings.accent_description')}</p>
        <div class="accent-row" role="group" aria-label={$t('settings.accent_title')}>
          {#each ACCENT_PRESETS as preset}
            <button
              type="button"
              class="accent-swatch"
              class:selected={$accentColor === preset.value.toLowerCase()}
              aria-label={$t(preset.key)}
              aria-pressed={$accentColor === preset.value.toLowerCase()}
              title={$t(preset.key)}
              style="--swatch:{preset.value}"
              onclick={() => applyAccentPreset(preset.value)}
            ></button>
          {/each}
          <label class="accent-custom">
            <input
              type="color"
              class="accent-picker"
              aria-label={$t('settings.accent_custom')}
              title={$t('settings.accent_custom')}
              value={$accentColor ?? '#10b981'}
              oninput={onCustomAccentInput}
            />
            <span>{$t('settings.accent_custom')}</span>
          </label>
          {#if $accentColor}
            <button
              type="button"
              class="accent-reset"
              aria-label={$t('settings.accent_reset')}
              title={$t('settings.accent_reset')}
              onclick={resetAccent}
            >
              <Icon name="cancel" size={14} />
              <span>{$t('settings.accent_reset')}</span>
            </button>
          {/if}
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

      <section aria-labelledby="settings-voice-output">
        <h3 id="settings-voice-output">{$t('settings.voice_output_title')}</h3>
        <p class="workspace-description">{$t('settings.voice_output_description')}</p>
        <p class="workspace-description" role="status">{$t('settings.voice_output_availability')}</p>
        <div class="choice-grid voice-grid" role="group" aria-label={$t('settings.voice_output_title')}>
          {#each ttsVoices as item}
            <div class="voice-option">
              <button
                type="button"
                class:selected={$voiceGender === item.gender}
                aria-label={$t(item.labelKey)}
                aria-pressed={$voiceGender === item.gender}
                title={$t(item.labelKey)}
                onclick={() => selectVoiceGender(item.gender)}
              >
                <Icon name="microphone" size={18} />
                <span>{$t(item.labelKey)}</span>
                <small>{$t(item.descriptionKey)}</small>
              </button>
              <button
                type="button"
                class="voice-preview-button"
                aria-label={$t('settings.voice_preview')}
                title={$t('settings.voice_preview')}
                onclick={() => previewVoiceGender(item.gender)}
              >
                <Icon name="play" size={14} />
                <span>{$t('settings.voice_preview')}</span>
              </button>
            </div>
          {/each}
        </div>
      </section>

      <section aria-labelledby="settings-workspace">
        <h3 id="settings-workspace">{$t('settings.workspace_title')}</h3>
        <p class="workspace-description">{$t('settings.workspace_description')}</p>
        <div class="workspace-card" data-workspace-status={$workspaceStore.status}>
          <div class="workspace-path">
            <span>{$t('settings.workspace_path')}</span>
            <output title={$workspaceStore.path ?? $t('settings.workspace_unconfirmed')}>
              {$workspaceStore.path ?? $t('settings.workspace_unconfirmed')}
            </output>
          </div>
          <button
            type="button"
            class="diagnostics-toggle workspace-button"
            disabled={$workspaceStore.status === 'confirming'}
            onclick={() => void chooseWorkspace()}
          >
            <Icon name="folder" size={18} />
            <span>{$t($workspaceStore.status === 'confirming' ? 'settings.workspace_selecting' : 'settings.workspace_choose')}</span>
          </button>
        </div>
        {#if $workspaceStore.error}
          <p class="workspace-error" role="alert">
            <strong>{$t('settings.workspace_error')}:</strong> {$workspaceStore.error}
          </p>
        {/if}
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
    <div class:panel-hidden={$settingsSection !== 'skills'} aria-hidden={$settingsSection !== 'skills'}>
      <SkillsManagerSection />
    </div>
    <div class:panel-hidden={$settingsSection !== 'permissions'} aria-hidden={$settingsSection !== 'permissions'}>
      <PermissionsSection />
    </div>
    <div class:panel-hidden={$settingsSection !== 'checkpoints'} aria-hidden={$settingsSection !== 'checkpoints'}>
      <CheckpointPanel />
    </div>
    <div class:panel-hidden={$settingsSection !== 'coding'} aria-hidden={$settingsSection !== 'coding'}>
      <CodingPanel />
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
            {#if !$filesCapabilityAvailable}<li>{$t('capability.files')}</li>{/if}
            <li>{$t('capability.vault')}</li>
            <li>{$t('capability.shell')}</li>
            <li>{$t('capability.external_tools')}</li>
          </ul>
        </div>
        <div>
          <h4>{$t('settings.pending_verification')}</h4>
          <ul>
            <li>{$t('capability.browser_pending')}</li>
            <li>{$t('capability.computer_use_pending')}</li>
            <li>{$t('capability.restart_recovery_pending')}</li>
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
    top: calc(var(--app-menubar-height) + var(--shell-header-height));
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
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-2) var(--lc-space-4);
  }

  .settings-tabs {
    position: sticky;
    top: 55px;
    z-index: 1;
    display: flex;
    gap: 2px;
    padding: var(--lc-space-2) var(--lc-space-3) 0;
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .settings-tabs button {
    flex: 1 1 0;
    min-width: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 34px;
    border: 0;
    border-bottom: 2px solid transparent;
    border-radius: 8px 8px 0 0;
    padding: 0 8px;
    background: transparent;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 640;
    white-space: nowrap;
    cursor: pointer;
    transition: background 0.16s ease, color 0.16s ease;
  }

  .settings-tabs button :global(svg) {
    opacity: 0.8;
    transition: opacity 0.16s ease;
  }

  .settings-tabs button:hover {
    background: color-mix(in srgb, var(--lc-text) 6%, transparent);
    color: var(--lc-text);
  }

  .settings-tabs button:hover :global(svg) {
    opacity: 1;
  }

  .settings-tabs button.active {
    border-bottom-color: var(--lc-accent);
    color: var(--lc-accent);
    font-weight: 720;
  }

  .settings-tabs button.active :global(svg) {
    opacity: 1;
  }

  .settings-tabs button span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .eyebrow {
    color: var(--lc-muted);
    font-size: 10px;
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
    font-size: 16px;
  }

  h3 {
    margin-bottom: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .close-button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-1);
    min-height: 32px;
    padding: 0 var(--lc-space-2);
    color: var(--lc-muted);
  }

  .settings-content {
    display: grid;
    gap: var(--lc-space-4);
    padding: var(--lc-space-4);
  }

  .settings-content > div:not(.panel-hidden) {
    display: grid;
    gap: var(--lc-space-4);
  }

  .panel-hidden {
    display: none;
  }

  section {
    min-width: 0;
    border-bottom: var(--border-thin);
    padding-bottom: var(--lc-space-4);
  }

  @media (max-width: 700px) {
    .settings-tabs button span {
      display: none;
    }

    .settings-tabs button {
      flex: 0 0 auto;
      min-width: 34px;
      padding: 0 10px;
    }
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

  .accent-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--lc-space-2);
  }

  .accent-swatch {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    border: 2px solid color-mix(in srgb, var(--lc-line) 70%, transparent);
    background: var(--swatch);
    cursor: pointer;
    transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
  }

  .accent-swatch:hover {
    transform: translateY(-1px) scale(1.06);
    border-color: var(--lc-line-strong);
  }

  .accent-swatch.selected {
    border-color: var(--lc-text);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--swatch) 45%, transparent);
  }

  .accent-custom {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 640;
    cursor: pointer;
  }

  .accent-picker {
    width: 34px;
    height: 34px;
    padding: 0;
    border: var(--border-thin);
    border-radius: 10px;
    background: var(--lc-panel-soft);
    cursor: pointer;
  }

  .accent-reset {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 0 var(--lc-space-2);
    border: var(--border-thin);
    border-radius: 10px;
    background: transparent;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 640;
    cursor: pointer;
    transition: color 0.16s ease, border-color 0.16s ease;
  }

  .accent-reset:hover {
    color: var(--lc-text);
    border-color: var(--lc-line-strong);
  }

  .voice-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .voice-option {
    min-width: 0;
    display: grid;
    gap: var(--lc-space-1);
  }

  .voice-option > button:first-child {
    min-height: 76px;
  }

  .voice-preview-button {
    grid-template-columns: auto 1fr;
    place-items: center start;
    min-height: 34px !important;
    padding: var(--lc-space-1) var(--lc-space-2) !important;
    text-align: left !important;
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

  .workspace-description {
    margin: 0 0 var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  .workspace-card {
    display: grid;
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  .workspace-path {
    display: grid;
    gap: var(--lc-space-1);
    min-width: 0;
  }

  .workspace-path > span {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 720;
  }

  .workspace-path output {
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .workspace-button {
    width: fit-content;
  }

  .workspace-error {
    margin: var(--lc-space-2) 0 0;
    color: var(--lc-danger);
    font-size: 11px;
    line-height: 1.4;
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

  .choice-grid button small {
    color: var(--lc-muted);
    font-size: 10px;
    font-weight: 560;
    line-height: 1.35;
  }

  .choice-grid button.selected small,
  .choice-grid button:hover small {
    color: inherit;
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

    .theme-grid,
    .voice-grid {
      grid-template-columns: 1fr;
    }

    .capability-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
