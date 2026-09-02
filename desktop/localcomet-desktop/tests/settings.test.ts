import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { LANGUAGES, setLocale } from '../src/lib/i18n';
import { controlPlaneStore, resetControlPlaneStore } from '../src/lib/stores/controlPlane';
import {
  resetShellStores,
  setDiagnosticsPanelOpen,
  setThemeMode,
  setVoiceGender
} from '../src/lib/stores/shellStore';

function settingsHtml(language: 'ru' | 'en' = 'ru'): string {
  setLocale(language);
  return render(SettingsPanel).body;
}

beforeEach(() => {
  resetControlPlaneStore();
  resetShellStores();
  setLocale('ru');
});

describe('minimal Settings surface', () => {
  it('renders the authorized Settings sections including the bounded Models manager', () => {
    const html = settingsHtml('en');
    for (const section of ['Appearance', 'Language', 'Diagnostics', 'Models', 'About']) {
      expect(html).toContain(section);
    }
    expect(html).toContain('Use approved catalog models or explicitly confirmed user-supplied GGUF models.');
    expect(html).toContain('assistant itself does not gain internet access');
    for (const excluded of ['API key', 'Account', 'Cloud', 'Telemetry']) {
      expect(html).not.toContain(excluded);
    }
  });

  it('exposes theme choices as semantic pressed buttons', () => {
    const html = settingsHtml('en');
    expect(html).toContain('title="System"');
    expect(html).toContain('title="Light"');
    expect(html).toContain('title="Dark"');
    expect(html.match(/aria-pressed=/g)?.length).toBeGreaterThanOrEqual(3);
  });

  it('exposes assistant voice choices with female selected by default', () => {
    const html = settingsHtml('en');
    expect(html).toContain('Assistant voice');
    expect(html).toContain('Current playback stops when you switch');
    expect(html).toContain('voice input stays unchanged');
    expect(html).toContain('Local speech output is currently available for Russian responses only');
    expect(html).toContain('title="Female voice"');
    expect(html).toContain('title="Male voice"');
    expect(html).toContain('Play sample');
    expect(html.match(/aria-label="Play sample"/g)?.length).toBe(2);
    expect(html).toMatch(/aria-pressed="true"[^>]*title="Female voice"/);
  });

  it('reflects a persisted male voice choice in Settings', () => {
    setVoiceGender('male');
    const html = settingsHtml('en');
    expect(html).toMatch(/aria-pressed="true"[^>]*title="Male voice"/);
    expect(html).toMatch(/aria-pressed="false"[^>]*title="Female voice"/);
  });

  it('exposes language choice as a labelled select listing every locale', () => {
    const html = settingsHtml('en');
    expect(html).toContain('aria-label="Select language"');
    expect(html).toContain('<select');
    // Endonyms: each language is offered in its own script.
    for (const endonym of ['Русский', 'English', 'Español', '日本語', '简体中文', 'العربية']) {
      expect(html).toContain(endonym);
    }
    const options = html.match(/<option /g)?.length ?? 0;
    expect(options).toBeGreaterThanOrEqual(LANGUAGES.length);
  });

  it('renders repository-proven About values', () => {
    const html = settingsHtml('en');
    expect(html).toContain('LocalComet');
    expect(html).toContain('v7.0.5');
    expect(html).toContain('v7.0.5b');
    expect(html).toContain('UNSIGNED_INTERNAL_BUILD');
  });

  it('shows localized read-only capability boundaries without enable controls', () => {
    const english = settingsHtml('en');
    for (const value of ['Current capabilities', 'Local chat', 'Local model inference', 'Internet', 'Email', 'Browser', 'Files', 'Vault', 'Computer Use', 'Shell', 'External tools']) {
      expect(english).toContain(value);
    }
    expect(english).toContain('Project context is currently unavailable.');
    expect(english).not.toContain('Enable internet');

    const russian = settingsHtml('ru');
    expect(russian).toContain('Текущие возможности');
    expect(russian).toContain('Локальная озвучка сейчас доступна только для ответов на русском языке');
    expect(russian).toContain('Контекст проекта недоступен');
  });

  it('shows the existing Control Plane state read-only', () => {
    controlPlaneStore.update((state) => ({ ...state, bridgeState: 'READY' }));
    const html = settingsHtml('en');
    expect(html).toContain('Control Plane: Connected');
    expect(html).toContain('<output');
  });

  it('reflects existing theme and Diagnostics state', () => {
    setThemeMode('dark');
    setDiagnosticsPanelOpen(true);
    const html = settingsHtml('en');
    expect(html).toMatch(/aria-pressed="true"[^>]*title="Dark"/);
    expect(html).toContain('Hide Diagnostics');
  });

  it('has a reachable close control and non-modal dialog semantics', () => {
    const html = settingsHtml('en');
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="false"');
    expect(html).toContain('aria-label="Close settings"');
  });
});
