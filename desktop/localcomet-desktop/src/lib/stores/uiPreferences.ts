import { isRecord } from '$lib/bridge/guards';
// locales.ts holds only the language registry and has no store imports, so
// importing it here cannot create a cycle with $lib/i18n/index.ts.
import { isLanguage, type Language } from '$lib/i18n/locales';
import { isEffortLevel, type EffortLevel } from '$lib/types/effort';
import { isComputeMode, type ComputeMode } from '$lib/types/computeMode';

export { isEffortLevel, type EffortLevel } from '$lib/types/effort';
export { isComputeMode, type ComputeMode } from '$lib/types/computeMode';

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
  internet: boolean;
}

export interface UiPreferences {
  theme: UiTheme;
  locale: UiLocale;
  diagnosticsPanel: DiagnosticsPanelPreference;
  agentPermissions: AgentPermissions;
  voiceMode: boolean;
  ctxSizeOverride: number | null;
  gpuLayersOverride: number | null;
  computeMode: ComputeMode;
  effort: EffortLevel;
}

export const DEFAULT_UI_PREFERENCES: Readonly<UiPreferences> = Object.freeze({
  theme: 'system',
  locale: 'ru',
  diagnosticsPanel: 'closed',
  voiceMode: false,
  agentPermissions: {
    files: true,
    shell: false,
    tools: true,
    computerUse: false,
    internet: false
  },
  ctxSizeOverride: null,
  gpuLayersOverride: null,
  computeMode: 'gpu',
  effort: 'off'
});

function defaultPreferences(): UiPreferences {
  return {
    ...DEFAULT_UI_PREFERENCES,
    agentPermissions: { ...DEFAULT_UI_PREFERENCES.agentPermissions }
  };
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
  const allowed = ['files', 'shell', 'tools', 'computerUse', 'internet'] as const;
  return Object.keys(value).every((key) => {
    if (!(allowed as readonly string[]).includes(key)) return false;
    return typeof value[key] === 'boolean';
  });
}

function normalizePreferences(value: unknown): UiPreferences {
  const preferences = defaultPreferences();
  if (!isRecord(value)) return preferences;

  if (isTheme(value.theme)) preferences.theme = value.theme;
  if (isLocale(value.locale)) preferences.locale = value.locale;
  if (isDiagnosticsPanel(value.diagnosticsPanel)) {
    preferences.diagnosticsPanel = value.diagnosticsPanel;
  }
  if (isEffortLevel(value.effort)) preferences.effort = value.effort;
  if (isComputeMode(value.computeMode)) preferences.computeMode = value.computeMode;
  if (typeof value.voiceMode === 'boolean') preferences.voiceMode = value.voiceMode;
  if (isAgentPermissions(value.agentPermissions)) {
    const nextPermissions = value.agentPermissions;
    for (const key of ['files', 'shell', 'tools', 'computerUse', 'internet'] as const) {
      if (typeof nextPermissions[key] === 'boolean') {
        preferences.agentPermissions[key] = nextPermissions[key] as boolean;
      }
    }
  }
  if (value.ctxSizeOverride === null || typeof value.ctxSizeOverride === 'number') {
    preferences.ctxSizeOverride = value.ctxSizeOverride;
  }
  if (value.gpuLayersOverride === null || typeof value.gpuLayersOverride === 'number') {
    preferences.gpuLayersOverride = value.gpuLayersOverride;
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
    if (typeof patch.voiceMode === 'boolean') preferences.voiceMode = patch.voiceMode;
    if (isDiagnosticsPanel(patch.diagnosticsPanel)) {
      preferences.diagnosticsPanel = patch.diagnosticsPanel;
    }
    if (isEffortLevel(patch.effort)) preferences.effort = patch.effort;
    if (isComputeMode(patch.computeMode)) preferences.computeMode = patch.computeMode;
    if (isAgentPermissions(patch.agentPermissions)) {
      preferences.agentPermissions = { ...preferences.agentPermissions, ...patch.agentPermissions } as AgentPermissions;
    }
    if (patch.ctxSizeOverride !== undefined) {
      preferences.ctxSizeOverride = patch.ctxSizeOverride;
    }
    if (patch.gpuLayersOverride !== undefined) {
      preferences.gpuLayersOverride = patch.gpuLayersOverride;
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
