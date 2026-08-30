import { beforeEach, describe, expect, it, vi } from 'vitest';

const invokeMock = vi.hoisted(() => vi.fn());

vi.mock('@tauri-apps/api/core', () => ({
  invoke: invokeMock
}));

import { claimSpeechRequest, speakLocalText, stopLocalText } from '../src/lib/bridge/voice';

describe('voice output lifecycle', () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue(undefined);
  });

  it('invokes the local speech command with Russian language', async () => {
    await speakLocalText('Проверочный ответ');

    expect(invokeMock).toHaveBeenCalledWith('speak_local_text', {
      text: 'Проверочный ответ',
      language: 'ru-RU',
      voice_profile: 'female'
    });
  });

  it('does not silently route English output through a Russian voice', async () => {
    await speakLocalText('English response', 'female', 'en');
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it('does not silently synthesize unsupported local languages with a Russian voice', async () => {
    await speakLocalText('Spanish response', 'female', 'es');
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it('passes the selected male profile to local speech without changing the input path', async () => {
    await speakLocalText('Мужской профиль', 'male');

    expect(invokeMock).toHaveBeenCalledWith('speak_local_text', {
      text: 'Мужской профиль',
      language: 'ru-RU',
      voice_profile: 'male'
    });
  });

  it('invokes the backend stop command and reports a successful cancellation', async () => {
    await expect(stopLocalText()).resolves.toBe(true);
    expect(invokeMock).toHaveBeenCalledWith('stop_local_text');
  });

  it('does not let a pending speak promise remain current after stop', async () => {
    let resolveSpeak: (() => void) | undefined;
    invokeMock.mockImplementationOnce(() => new Promise<void>((resolve) => {
      resolveSpeak = resolve;
    }));

    const pending = speakLocalText('Старый ответ');
    await Promise.resolve();
    await expect(stopLocalText()).resolves.toBe(true);
    resolveSpeak?.();
    await expect(pending).resolves.toBeUndefined();

    expect(invokeMock.mock.calls.map((call) => call[0])).toEqual(['speak_local_text', 'stop_local_text']);
  });

  it('switches from a cancelled female request to a new male request', async () => {
    let resolveSpeak: (() => void) | undefined;
    invokeMock.mockImplementationOnce(() => new Promise<void>((resolve) => {
      resolveSpeak = resolve;
    }));

    const female = speakLocalText('Женский ответ', 'female');
    await Promise.resolve();
    await expect(stopLocalText()).resolves.toBe(true);
    resolveSpeak?.();
    await female;
    await speakLocalText('Мужской ответ', 'male', 'ru');

    expect(invokeMock.mock.calls[0]).toEqual(['speak_local_text', {
      text: 'Женский ответ',
      language: 'ru-RU',
      voice_profile: 'female'
    }]);
    expect(invokeMock.mock.calls[1]).toEqual(['stop_local_text']);
    expect(invokeMock.mock.calls[2]).toEqual(['speak_local_text', {
      text: 'Мужской ответ',
      language: 'ru-RU',
      voice_profile: 'male'
    }]);
  });

  it('does not claim the same completed request twice, including after a remount', () => {
    expect(claimSpeechRequest('voice-regression-request-1')).toBe(true);
    expect(claimSpeechRequest('voice-regression-request-1')).toBe(false);
    expect(claimSpeechRequest('voice-regression-request-2')).toBe(true);
  });

  it('reports an IPC failure instead of pretending stop succeeded', async () => {
    invokeMock.mockRejectedValueOnce(new Error('command unavailable'));

    await expect(stopLocalText()).resolves.toBe(false);
    expect(invokeMock).toHaveBeenCalledWith('stop_local_text');
  });
});
