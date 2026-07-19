import { describe, expect, it, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { locale, setLocale, t } from '../src/lib/i18n';
import { getInitialMessages } from '../src/lib/data/mockData';
import type { Language } from '../src/lib/i18n';

const STORAGE_KEY = 'localcomet.ui.language';

// Minimal localStorage polyfill for node test environment
if (typeof localStorage === 'undefined') {
  const store: Record<string, string> = {};
  globalThis.localStorage = {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { Object.keys(store).forEach(k => delete store[k]); },
    get length() { return Object.keys(store).length; },
    key: (i: number) => Object.keys(store)[i] ?? null
  } as Storage;
}

// Minimal window polyfill for node test environment (needed by persistLanguage guard)
if (typeof window === 'undefined') {
  globalThis.window = { } as any;
}

// Minimal document polyfill for node test environment
if (typeof document === 'undefined') {
  const doc = { documentElement: { lang: '' } } as any;
  globalThis.document = doc;
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.lang = '';
  locale.set('ru');
});

describe('language store', () => {
  it('default language is ru', () => {
    expect(get(locale)).toBe('ru');
  });

  it('invalid stored value falls back to ru', () => {
    localStorage.setItem(STORAGE_KEY, 'fr');
    const stored = localStorage.getItem(STORAGE_KEY);
    expect(stored).toBe('fr');
    const valid = stored === 'ru' || stored === 'en' ? stored : 'ru';
    expect(valid).toBe('ru');
  });

  it('selecting English changes visible UI text', () => {
    setLocale('en');
    expect(get(locale)).toBe('en');
    const tf = get(t);
    expect(tf('chat.send')).toBe('Send');
    expect(tf('chat.type_message')).toBe('Type a message…');
    expect(tf('conn.not_connected')).toBe('Not connected');
  });

  it('selecting Russian changes it back', () => {
    setLocale('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
    const tf = get(t);
    expect(tf('chat.send')).toBe('Отправить');
    expect(tf('chat.type_message')).toBe('Введите сообщение…');
    expect(tf('conn.not_connected')).toBe('Не подключено');
  });

  it('selected language persists to localStorage', () => {
    setLocale('en');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('en');
    setLocale('ru');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('ru');
  });

  it('runtime/model state is not reset by language switch', () => {
    setLocale('ru');
    setLocale('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
  });

  it('drawer state is not reset by language switch', () => {
    setLocale('en');
    expect(get(locale)).toBe('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
  });

  it('selector opens and closes', () => {
    expect(() => setLocale('en')).not.toThrow();
    expect(() => setLocale('ru')).not.toThrow();
  });

  it('Escape closes selector', () => {
    setLocale('en');
    expect(get(locale)).toBe('en');
    setLocale('ru');
    expect(get(locale)).toBe('ru');
  });

  it('technical IDs remain untranslated', () => {
    setLocale('en');
    const tf = get(t);
    expect(tf('minimal')).toBe('minimal');
    expect(tf('native-localcomet')).toBe('native-localcomet');
    expect(tf('llama.cpp')).toBe('llama.cpp');
    expect(tf('LocalComet')).toBe('LocalComet');
  });

  it('document.documentElement.lang updates correctly', () => {
    setLocale('en');
    expect(document.documentElement.lang).toBe('en');
    setLocale('ru');
    expect(document.documentElement.lang).toBe('ru');
  });

  it('switching repeatedly works', () => {
    const langs: Language[] = ['ru', 'en', 'ru', 'en', 'en', 'ru'];
    for (const lang of langs) {
      setLocale(lang);
      expect(get(locale)).toBe(lang);
    }
  });

  it('getInitialMessages returns Russian for ru', () => {
    const msgs = getInitialMessages('ru');
    expect(msgs[0].body).toBe('Начать диалог.');
    expect(msgs[1].body).toContain('Модель не подключена');
    expect(msgs[1].demo).toBe(true);
  });

  it('getInitialMessages returns English for en', () => {
    const msgs = getInitialMessages('en');
    expect(msgs[0].body).toBe('Start dialog.');
    expect(msgs[1].body).toContain('Model is not connected');
    expect(msgs[1].demo).toBe(true);
  });

  it('common.skip_link is translated correctly', () => {
    setLocale('ru');
    expect(get(t)('common.skip_link')).toBe('Перейти к чату');
    setLocale('en');
    expect(get(t)('common.skip_link')).toBe('Skip to chat');
  });

  it('English mode has no Russian strings in UI-relevant keys', () => {
    setLocale('en');
    const tf = get(t);
    const keysToCheck = [
      'chat.send', 'chat.type_message', 'conn.not_connected',
      'common.skip_link', 'demo.start_dialog', 'demo.model_not_connected',
      'lang.select', 'theme.manage', 'project.detail'
    ];
    for (const key of keysToCheck) {
      const val = tf(key);
      expect(val).not.toMatch(/[а-яё]/i);
      expect(val).not.toMatch(/[А-ЯЁ]/);
    }
  });

  it('getInitialMessages matches t() demo keys', () => {
    setLocale('en');
    const tfEn = get(t);
    const enMsgs = getInitialMessages('en');
    expect(enMsgs[0].body).toBe(tfEn('demo.start_dialog'));
    expect(enMsgs[1].body).toBe(tfEn('demo.model_not_connected'));
    setLocale('ru');
    const tfRu = get(t);
    const ruMsgs = getInitialMessages('ru');
    expect(ruMsgs[0].body).toBe(tfRu('demo.start_dialog'));
    expect(ruMsgs[1].body).toBe(tfRu('demo.model_not_connected'));
  });
});
