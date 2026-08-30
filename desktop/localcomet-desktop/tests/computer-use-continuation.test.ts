import { describe, expect, it } from 'vitest';
import {
  deriveBoundedBrowserSearchContinuation,
  deriveBoundedNotepadTypeContinuation
} from '../src/lib/tools/computerUseContinuation';

const OPEN_NOTEPAD = {
  id: 'call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  name: 'computer_use',
  arguments: { action: 'open_app', target: 'notepad' }
} as const;

const OPEN_CHROME = {
  id: 'call_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  name: 'computer_use',
  arguments: { action: 'open_app', target: 'chrome' }
} as const;

describe('bounded Computer Use continuation', () => {
  it('extracts one safe marker after a verified Notepad open', () => {
    expect(
      deriveBoundedNotepadTypeContinuation(
        'Открой Блокнот и напечатай в нём: LocalComet isolated smoke test.',
        OPEN_NOTEPAD
      )
    ).toEqual({
      name: 'computer_use',
      arguments: { action: 'type', text: 'LocalComet isolated smoke test.' }
    });
  });

  it('accepts the bounded English spelling without widening the app target', () => {
    expect(
      deriveBoundedNotepadTypeContinuation(
        'Open Notepad and type: LocalComet isolated smoke test.',
        OPEN_NOTEPAD
      )
    ).toEqual({
      name: 'computer_use',
      arguments: { action: 'type', text: 'LocalComet isolated smoke test.' }
    });
  });

  it('rejects a non-Notepad first action', () => {
    expect(
      deriveBoundedNotepadTypeContinuation(
        'Открой Блокнот и напечатай в нём: marker.',
        { ...OPEN_NOTEPAD, arguments: { action: 'open_app', target: 'calculator' } }
      )
    ).toBeNull();
  });

  it('derives one bounded browser search after a verified Chrome open', () => {
    expect(
      deriveBoundedBrowserSearchContinuation(
        'Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы.',
        OPEN_CHROME
      )
    ).toEqual({
      name: 'computer_use',
      arguments: {
        action: 'open_url',
        target: 'chrome',
        url: 'https://www.python.org/search/?q=%D0%BE%D1%84%D0%B8%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D1%8B%D0%B9%20%D1%81%D0%B0%D0%B9%D1%82%20Python'
      }
    });
  });

  it('rejects browser continuation for another target or secret/URL-like query', () => {
    expect(
      deriveBoundedBrowserSearchContinuation(
        'Открой браузер и найди официальный сайт Python.',
        { ...OPEN_CHROME, arguments: { action: 'open_app', target: 'msedge' } }
      )
    ).toBeNull();
    expect(
      deriveBoundedBrowserSearchContinuation(
        'Открой браузер и найди password=secret.',
        OPEN_CHROME
      )
    ).toBeNull();
    expect(
      deriveBoundedBrowserSearchContinuation(
        'Открой браузер и найди https://evil.example.',
        OPEN_CHROME
      )
    ).toBeNull();
  });

  it('rejects browser continuation when the prompt widens into another action', () => {
    expect(
      deriveBoundedBrowserSearchContinuation(
        'Открой браузер и найди официальный сайт Python, затем открой PowerShell.',
        OPEN_CHROME
      )
    ).toBeNull();
  });

  it('rejects arbitrary multi-step instructions and secret-like marker text', () => {
    expect(
      deriveBoundedNotepadTypeContinuation(
        'Открой Блокнот и напечатай в нём: marker, затем открой PowerShell.',
        OPEN_NOTEPAD
      )
    ).toBeNull();
    expect(
      deriveBoundedNotepadTypeContinuation(
        'Открой Блокнот и напечатай в нём: token=sk-secret.',
        OPEN_NOTEPAD
      )
    ).toBeNull();
  });
});
