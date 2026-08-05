import { writable, derived } from 'svelte/store';
import { ru } from './ru';
import { en } from './en';
import { es } from './es';
import { de } from './de';
import { fr } from './fr';
import { ptBR } from './pt-BR';
import { it } from './it';
import { zhCN } from './zh-CN';
import { ja } from './ja';
import { ko } from './ko';
import { tr } from './tr';
import { uk } from './uk';
import { pl } from './pl';
import { ar } from './ar';
import { LANGUAGES, isLanguage, languageDescriptor, type Language } from './locales';
import { loadUiPreferences, updateUiPreferences } from '$lib/stores/uiPreferences';

export type { Language, LanguageDescriptor } from './locales';
export { LANGUAGES, isLanguage, languageDescriptor } from './locales';

export type TranslationMap = Record<string, string>;

const DICTIONARIES: Readonly<Record<Language, TranslationMap>> = Object.freeze({
  ru,
  en,
  es,
  de,
  fr,
  'pt-BR': ptBR,
  it,
  'zh-CN': zhCN,
  ja,
  ko,
  tr,
  uk,
  pl,
  ar
});

function getInitialLanguage(): Language {
  return loadUiPreferences().locale;
}

function applyDocumentLanguage(lang: Language): void {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = lang;
  document.documentElement.dir = languageDescriptor(lang).dir;
}

export const locale = writable<Language>(getInitialLanguage());

/**
 * Resolve a key for the active locale.
 *
 * Partially translated locales cover the application chrome only, so lookup
 * falls back to English and then to the key itself. Without this chain a
 * partial locale would render raw identifiers such as `models.custom_title`.
 */
export const t = derived(locale, ($locale) => {
  const primary: TranslationMap = DICTIONARIES[$locale] ?? ru;
  applyDocumentLanguage($locale);
  return (key: string): string => primary[key] ?? en[key] ?? key;
});

export function setLocale(lang: Language): void {
  if (!isLanguage(lang)) return;
  locale.set(lang);
  updateUiPreferences({ locale: lang });
  applyDocumentLanguage(lang);
}

/** Languages offered in the picker, in registry order. */
export const availableLanguages = LANGUAGES;

/**
 * Map an interface language onto a locale the assistant backend accepts.
 *
 * The Rust control plane validates the turn locale against `ru | en`
 * (src-tauri/src/control_plane.rs) and the prompt scaffolding only exists in
 * those two languages. Interface chrome may be shown in any registered
 * language, but a model turn must still declare a supported locale, so
 * everything other than Russian is sent as English. Widening the backend enum
 * instead would claim prompt support that does not exist.
 */
export function assistantLocaleFor(lang: Language): 'ru' | 'en' {
  return lang === 'ru' ? 'ru' : 'en';
}
