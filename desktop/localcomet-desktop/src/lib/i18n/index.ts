import { writable, derived } from 'svelte/store';
import { ru } from './ru';
import { en } from './en';
import { loadUiPreferences, updateUiPreferences } from '$lib/stores/uiPreferences';

export type Language = 'ru' | 'en';
export type TranslationMap = Record<string, string>;

function getInitialLanguage(): Language {
  return loadUiPreferences().locale;
}

function setDocumentLang(lang: Language): void {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = lang;
}

export const locale = writable<Language>(getInitialLanguage());

export const t = derived(locale, ($locale) => {
  const map: TranslationMap = $locale === 'en' ? en : ru;
  setDocumentLang($locale);
  return (key: string): string => map[key] ?? key;
});

export function setLocale(lang: Language): void {
  if (lang !== 'ru' && lang !== 'en') return;
  locale.set(lang);
  updateUiPreferences({ locale: lang });
  setDocumentLang(lang);
}
