// locales.ts holds only the language registry and has no store imports, so
// importing it here cannot create a cycle with $lib/i18n/index.ts.
import { isLanguage, type Language } from '$lib/i18n/locales';

export const UI_PREFERENCES_KEY = 'localcomet.ui.preferences.v1';
export const LEGACY_LANGUAGE_KEY = 'localcomet.ui.language';

export type UiTheme = 'system' | 'light' | 'dark';

/**
 * Interface locale codes. The canonical list lives in $lib/i18n/locales so the
 * picker, the translation registry and this validator cannot drift apart.
 */
export type UiLocale = Language;
export type DiagnosticsPanelPreference = 'open' | 'closed';

export interface AgentPermissions {
  files: boolean;
  shell: boolean;
  tools: boolean;
  computerUse: boolean;
}

export interface UiPreferences {
  theme: UiTheme;
  locale: UiLocale;
  diagnosticsPanel: DiagnosticsPanelPreference;
  agentPermissions: AgentPermissions;
}

export const DEFAULT_UI_PREFERENCES: Readonly<UiPreferences> = Object.freeze({
  theme: 'system',
  locale: 'ru',
  diagnosticsPanel: 'closed',
  agentPermissions: {
    files: true,
    shell: false,
    tools: true,
    computerUse: false
  }
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
  return isLanguage(value);
}

function isDiagnosticsPanel(value: unknown): value is DiagnosticsPanelPreference {
  return value === 'open' || value === 'closed';
}

function isAgentPermissions(value: unknown): value is Partial<AgentPermissions> {
  if (!isRecord(value)) return false;
  return typeof value.files === 'boolean' || 
         typeof value.shell === 'boolean' || 
         typeof value.tools === 'boolean' ||
         typeof value.computerUse === 'boolean';
}

function normalizePreferences(value: unknown): UiPreferences {
  const preferences = defaultPreferences();
  if (!isRecord(value)) return preferences;

  if (isTheme(value.theme)) preferences.theme = value.theme;
  if (isLocale(value.locale)) preferences.locale = value.locale;
  if (isDiagnosticsPanel(value.diagnosticsPanel)) {
    preferences.diagnosticsPanel = value.diagnosticsPanel;
  }
  if (isAgentPermissions(value.agentPermissions)) {
    preferences.agentPermissions = { ...preferences.agentPermissions, ...value.agentPermissions } as AgentPermissions;
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
