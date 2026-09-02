import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import StartupScreen from '../src/lib/components/startup/StartupScreen.svelte';
import { setLocale } from '../src/lib/i18n';

function startupHtml(language: 'ru' | 'en', props: { timedOut?: boolean } = {}): string {
  setLocale(language);
  return render(StartupScreen, { props }).body;
}

describe('StartupScreen bounded startup', () => {
  it('does not show the timeout escape hatch while startup is in progress', () => {
    const html = startupHtml('ru');
    expect(html).toContain('startup-screen');
    expect(html).not.toContain('startup-timeout');
    expect(html).not.toContain('startup-continue');
  });

  it('shows the timeout text and the continue button when timed out (ru)', () => {
    const html = startupHtml('ru', { timedOut: true });
    expect(html).toContain('Запуск дольше обычного');
    expect(html).toContain('Продолжить');
    expect(html).toContain('startup-continue');
  });

  it('shows the timeout text and the continue button when timed out (en)', () => {
    const html = startupHtml('en', { timedOut: true });
    expect(html).toContain('taking longer than usual');
    expect(html).toContain('Continue');
    expect(html).toContain('startup-continue');
  });
});
