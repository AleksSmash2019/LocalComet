import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import EffortSelector from '../src/lib/components/chat/EffortSelector.svelte';
import ModelSetupDrawer from '../src/lib/components/model/ModelSetupDrawer.svelte';
import OnboardingScreen from '../src/lib/components/onboarding/OnboardingScreen.svelte';
import { resetModelGatewayStore } from '../src/lib/stores/modelGateway';
import { modelSetupMode, resetShellStores } from '../src/lib/stores/shellStore';

describe('hidden user-journey quality contracts', () => {
  beforeEach(() => {
    resetModelGatewayStore();
    resetShellStores();
    modelSetupMode.set('managed');
  });

  it('renders one explicit next action on first run instead of a dead-end checklist', () => {
    const html = render(OnboardingScreen).body;
    expect(html).toContain('Следующий шаг');
    expect(html).toContain('Выбрать и запустить модель');
    expect(html).not.toContain('Запустить демо');
  });

  it('makes the current effort level discoverable next to the composer', () => {
    const html = render(EffortSelector).body;
    expect(html).toContain('Режим размышления');
    expect(html).toContain('Выкл.');
    expect(html).toContain('aria-haspopup="listbox"');
  });

  it('keeps voice failure in context instead of introducing a blocking browser alert', () => {
    const html = render(MessageComposer).body;
    expect(html).toContain('aria-pressed="false"');
    expect(html).not.toContain('role="alert"');
  });

  it('discloses selected model and automatic engine behavior in the managed setup path', () => {
    const html = render(ModelSetupDrawer).body;
    expect(html).toContain('Рекомендуемый путь');
    expect(html).toContain('aria-modal="true"');
  });

  it('keeps the composer model-gated and keyboard-addressable', () => {
    const html = render(MessageComposer).body;
    expect(html).toContain('id="composer-draft"');
    expect(html).toContain('aria-label="Введите сообщение…"');
    expect(html).toContain('aria-pressed="false"');
  });
});
