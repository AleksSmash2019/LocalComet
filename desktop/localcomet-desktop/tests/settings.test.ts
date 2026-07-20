import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { setLocale } from '../src/lib/i18n';
import { controlPlaneStore, resetControlPlaneStore } from '../src/lib/stores/controlPlane';
import {
  resetShellStores,
  setDiagnosticsPanelOpen,
  setThemeMode
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
  it('renders only the authorized Settings sections', () => {
    const html = settingsHtml('en');
    for (const section of ['Appearance', 'Language', 'Diagnostics', 'About']) {
      expect(html).toContain(section);
    }
    for (const excluded of ['API key', 'Account', 'Cloud', 'Telemetry', 'Model download']) {
      expect(html).not.toContain(excluded);
    }
  });

  it('exposes theme and language choices as semantic pressed buttons', () => {
    const html = settingsHtml('en');
    expect(html).toContain('title="System"');
    expect(html).toContain('title="Light"');
    expect(html).toContain('title="Dark"');
    expect(html).toContain('title="Русский"');
    expect(html).toContain('title="English"');
    expect(html.match(/aria-pressed=/g)?.length).toBeGreaterThanOrEqual(6);
  });

  it('renders repository-proven About values', () => {
    const html = settingsHtml('en');
    expect(html).toContain('LocalComet');
    expect(html).toContain('v6.84.5.1');
    expect(html).toContain('v6.84.5.1b');
    expect(html).toContain('UNSIGNED_INTERNAL_BUILD');
  });

  it('shows localized read-only capability boundaries without enable controls', () => {
    const english = settingsHtml('en');
    for (const value of ['Current capabilities', 'Local chat', 'Local model inference', 'Internet', 'Email', 'Browser', 'Files', 'Vault', 'Computer Use', 'Shell', 'External tools']) {
      expect(english).toContain(value);
    }
    expect(english).toContain('Project-specific context is not supplied');
    expect(english).not.toContain('Enable internet');

    const russian = settingsHtml('ru');
    expect(russian).toContain('Текущие возможности');
    expect(russian).toContain('Контекст проекта не предоставлен');
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
