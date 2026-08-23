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

  it('invokes the local Piper speech command with Russian language', async () => {
    await speakLocalText('Проверочный ответ');

    expect(invokeMock).toHaveBeenCalledWith('speak_local_text', {
      text: 'Проверочный ответ',
      language: 'ru-RU'
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
