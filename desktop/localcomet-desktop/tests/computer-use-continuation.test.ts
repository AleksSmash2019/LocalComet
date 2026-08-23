import { describe, expect, it } from 'vitest';
import { deriveBoundedNotepadTypeContinuation } from '../src/lib/tools/computerUseContinuation';

const OPEN_NOTEPAD = {
  id: 'call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  name: 'computer_use',
  arguments: { action: 'open_app', target: 'notepad' }
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
