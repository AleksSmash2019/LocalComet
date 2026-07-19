import { writable, derived } from 'svelte/store';
import { ru } from './ru';
import { en } from './en';

export type Language = 'ru' | 'en';
export type TranslationMap = Record<string, string>;

const STORAGE_KEY = 'localcomet.ui.language';

function getInitialLanguage(): Language {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') return 'ru';
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'ru' || stored === 'en') return stored;
  } catch {
    // localStorage unavailable (SSR, test, privacy mode)
  }
  return 'ru';
}

function persistLanguage(lang: Language): void {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // silent
  }
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
  locale.set(lang);
  persistLanguage(lang);
  setDocumentLang(lang);
}
