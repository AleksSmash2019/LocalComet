import { beforeEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_UI_PREFERENCES,
  LEGACY_LANGUAGE_KEY,
  UI_PREFERENCES_KEY,
  loadUiPreferences,
  updateUiPreferences
} from '../src/lib/stores/uiPreferences';

function createMemoryStorage(initial: Record<string, string> = {}): Storage {
  const values = new Map(Object.entries(initial));
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => { values.delete(key); },
    setItem: (key: string, value: string) => { values.set(key, value); }
  };
}

function installStorage(storage: Storage): void {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage
  });
}

describe('UI preferences', () => {
  beforeEach(() => {
    installStorage(createMemoryStorage());
  });

  it('uses a versioned key and complete safe defaults', () => {
    expect(UI_PREFERENCES_KEY).toBe('localcomet.ui.preferences.v1');
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
    expect(Object.keys(loadUiPreferences())).toEqual(['theme', 'locale', 'diagnosticsPanel']);
  });

  it('loads only valid fields and ignores unknown fields', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open',
      repositoryPath: 'C:\\private',
      futureField: true
    }));
    expect(loadUiPreferences()).toEqual({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    });
  });

  it('defaults invalid and missing fields independently', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'sepia',
      locale: 'en',
      diagnosticsPanel: 'floating'
    }));
    expect(loadUiPreferences()).toEqual({
      theme: 'system',
      locale: 'en',
      diagnosticsPanel: 'closed'
    });
  });

  it('falls back safely for malformed or non-object records', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, '{');
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify(['dark', 'en', 'open']));
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
  });

  it('reads the legacy language only when the v1 record is absent', () => {
    localStorage.setItem(LEGACY_LANGUAGE_KEY, 'en');
    expect(loadUiPreferences()).toEqual({
      theme: 'system',
      locale: 'en',
      diagnosticsPanel: 'closed'
    });
    expect(localStorage.getItem(UI_PREFERENCES_KEY)).toBeNull();
    expect(localStorage.getItem(LEGACY_LANGUAGE_KEY)).toBe('en');

    localStorage.setItem(UI_PREFERENCES_KEY, '{');
    expect(loadUiPreferences().locale).toBe('ru');
  });

  it('writes a complete bounded record while preserving valid current fields', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'closed'
    }));
    expect(updateUiPreferences({ diagnosticsPanel: 'open' })).toEqual({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    });
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}')).toEqual({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    });
  });

  it('ignores invalid and unknown update fields', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'light',
      locale: 'ru',
      diagnosticsPanel: 'open'
    }));
    // 'kl' is deliberately not a registered interface language; 'fr' used to
    // serve that role but is now a real locale.
    const unsafePatch = {
      theme: 'sepia',
      locale: 'kl',
      diagnosticsPanel: 'floating',
      prompt: 'do not persist'
    } as unknown as Parameters<typeof updateUiPreferences>[0];
    expect(updateUiPreferences(unsafePatch)).toEqual({
      theme: 'light',
      locale: 'ru',
      diagnosticsPanel: 'open'
    });
    expect(Object.keys(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}'))).toEqual([
      'theme',
      'locale',
      'diagnosticsPanel'
    ]);
  });

  it('never writes or removes the legacy language key', () => {
    localStorage.setItem(LEGACY_LANGUAGE_KEY, 'en');
    updateUiPreferences({ theme: 'dark' });
    expect(localStorage.getItem(LEGACY_LANGUAGE_KEY)).toBe('en');
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}').locale).toBe('en');
  });

  it('survives storage read and write failures', () => {
    installStorage({
      get length() { return 0; },
      clear: () => undefined,
      getItem: () => { throw new Error('blocked'); },
      key: () => null,
      removeItem: () => undefined,
      setItem: () => { throw new Error('blocked'); }
    });
    expect(() => loadUiPreferences()).not.toThrow();
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
    expect(() => updateUiPreferences({ theme: 'dark' })).not.toThrow();
    expect(updateUiPreferences({ theme: 'dark' }).theme).toBe('dark');
  });
});
