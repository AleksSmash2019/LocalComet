/**
 * Registry of interface languages.
 *
 * `ru` and `en` are complete (every key translated). The remaining locales
 * translate the application chrome — navigation, sidebar, settings, command
 * palette, theme and language controls — and fall back to English for the
 * deeper operational surfaces (model manager, diagnostics, approvals). The
 * fallback is resolved in index.ts, so a missing key never renders as a raw
 * identifier.
 *
 * Language names are endonyms (each shown in its own language), which is the
 * convention used by other AI products and avoids an N x N translation matrix
 * for the picker itself.
 */
export type Language =
  | 'ru'
  | 'en'
  | 'es'
  | 'de'
  | 'fr'
  | 'pt-BR'
  | 'it'
  | 'zh-CN'
  | 'ja'
  | 'ko'
  | 'tr'
  | 'uk'
  | 'pl'
  | 'ar';

export interface LanguageDescriptor {
  /** BCP-47 code used for storage and the document lang attribute. */
  readonly code: Language;
  /** Native name shown in the picker. */
  readonly endonym: string;
  /** True when every translation key is present in this locale. */
  readonly complete: boolean;
  /** Writing direction; only Arabic is right-to-left here. */
  readonly dir: 'ltr' | 'rtl';
}

export const LANGUAGES: readonly LanguageDescriptor[] = Object.freeze([
  { code: 'ru', endonym: 'Русский', complete: true, dir: 'ltr' },
  { code: 'en', endonym: 'English', complete: true, dir: 'ltr' },
  { code: 'es', endonym: 'Español', complete: false, dir: 'ltr' },
  { code: 'de', endonym: 'Deutsch', complete: false, dir: 'ltr' },
  { code: 'fr', endonym: 'Français', complete: false, dir: 'ltr' },
  { code: 'pt-BR', endonym: 'Português (Brasil)', complete: false, dir: 'ltr' },
  { code: 'it', endonym: 'Italiano', complete: false, dir: 'ltr' },
  { code: 'zh-CN', endonym: '简体中文', complete: false, dir: 'ltr' },
  { code: 'ja', endonym: '日本語', complete: false, dir: 'ltr' },
  { code: 'ko', endonym: '한국어', complete: false, dir: 'ltr' },
  { code: 'tr', endonym: 'Türkçe', complete: false, dir: 'ltr' },
  { code: 'uk', endonym: 'Українська', complete: false, dir: 'ltr' },
  { code: 'pl', endonym: 'Polski', complete: false, dir: 'ltr' },
  { code: 'ar', endonym: 'العربية', complete: false, dir: 'rtl' }
]);

const BY_CODE = new Map<string, LanguageDescriptor>(
  LANGUAGES.map((entry) => [entry.code, entry])
);

export function isLanguage(value: unknown): value is Language {
  return typeof value === 'string' && BY_CODE.has(value);
}

export function languageDescriptor(code: Language): LanguageDescriptor {
  const found = BY_CODE.get(code);
  if (!found) throw new Error(`unknown language: ${code}`);
  return found;
}
