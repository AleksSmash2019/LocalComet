export const UI_PREFERENCES_KEY = 'localcomet.ui.preferences.v1';
export const LEGACY_LANGUAGE_KEY = 'localcomet.ui.language';

export type UiTheme = 'system' | 'light' | 'dark';
export type UiLocale = 'ru' | 'en';
export type DiagnosticsPanelPreference = 'open' | 'closed';

export interface UiPreferences {
  theme: UiTheme;
  locale: UiLocale;
  diagnosticsPanel: DiagnosticsPanelPreference;
}

export const DEFAULT_UI_PREFERENCES: Readonly<UiPreferences> = Object.freeze({
  theme: 'system',
  locale: 'ru',
  diagnosticsPanel: 'closed'
});

function defaultPreferences(): UiPreferences {
  return { ...DEFAULT_UI_PREFERENCES };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isTheme(value: unknown): value is UiTheme {
  return value === 'system' || value === 'light' || value === 'dark';
}

function isLocale(value: unknown): value is UiLocale {
  return value === 'ru' || value === 'en';
}

function isDiagnosticsPanel(value: unknown): value is DiagnosticsPanelPreference {
  return value === 'open' || value === 'closed';
}

function normalizePreferences(value: unknown): UiPreferences {
  const preferences = defaultPreferences();
  if (!isRecord(value)) return preferences;

  if (isTheme(value.theme)) preferences.theme = value.theme;
  if (isLocale(value.locale)) preferences.locale = value.locale;
  if (isDiagnosticsPanel(value.diagnosticsPanel)) {
    preferences.diagnosticsPanel = value.diagnosticsPanel;
  }
  return preferences;
}

function browserStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

function legacyLocale(storage: Storage): UiLocale | null {
  try {
    const value = storage.getItem(LEGACY_LANGUAGE_KEY);
    return isLocale(value) ? value : null;
  } catch {
    return null;
  }
}

export function loadUiPreferences(): UiPreferences {
  const storage = browserStorage();
  if (!storage) return defaultPreferences();

  let serialized: string | null;
  try {
    serialized = storage.getItem(UI_PREFERENCES_KEY);
  } catch {
    return defaultPreferences();
  }

  if (serialized === null) {
    const preferences = defaultPreferences();
    preferences.locale = legacyLocale(storage) ?? preferences.locale;
    return preferences;
  }

  try {
    return normalizePreferences(JSON.parse(serialized) as unknown);
  } catch {
    return defaultPreferences();
  }
}

export function updateUiPreferences(patch: Readonly<Partial<UiPreferences>>): UiPreferences {
  const preferences = loadUiPreferences();

  if (isRecord(patch)) {
    if (isTheme(patch.theme)) preferences.theme = patch.theme;
    if (isLocale(patch.locale)) preferences.locale = patch.locale;
    if (isDiagnosticsPanel(patch.diagnosticsPanel)) {
      preferences.diagnosticsPanel = patch.diagnosticsPanel;
    }
  }

  const storage = browserStorage();
  if (storage) {
    try {
      storage.setItem(UI_PREFERENCES_KEY, JSON.stringify(preferences));
    } catch {
      // Browser storage can be unavailable or full; the in-memory caller still succeeds.
    }
  }

  return preferences;
}
