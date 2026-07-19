import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import { locale, setLocale, t } from '../src/lib/i18n';
import { controlPlaneStore, resetControlPlaneStore } from '../src/lib/stores/controlPlane';
import { modelGatewayStore, resetModelGatewayStore } from '../src/lib/stores/modelGateway';
import {
  activeInspectorSection,
  inspectorVisible,
  resetShellStores,
  setActiveInspectorSection
} from '../src/lib/stores/shellStore';

function diagnosticsHtml(language: 'ru' | 'en'): string {
  setLocale(language);
  return render(Diagnostics).body;
}

beforeEach(() => {
  resetControlPlaneStore();
  resetModelGatewayStore();
  resetShellStores();
  locale.set('ru');
});

describe('Diagnostics localization closure', () => {
  it('removes the known reachable English chrome from Russian Diagnostics', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    const html = diagnosticsHtml('ru');
    for (const gap of [
      'Runtime', 'Event Stream', 'No validated events received.', 'Policy Decision',
      'Not evaluated', 'Binding required', 'Off', 'Unavailable'
    ]) {
      expect(html).not.toContain(gap);
    }
  });

  it('renders the required English Diagnostics chrome', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    const html = diagnosticsHtml('en');
    for (const text of [
      'Runtime State', 'EVENT STREAM', 'No validated events received.', 'POLICY DECISION',
      'Not evaluated', 'Binding required', 'Off'
    ]) {
      expect(html).toContain(text);
    }
  });

  it('translates Runtime State to Состояние системы', () => {
    expect(diagnosticsHtml('en')).toContain('Runtime State');
    expect(diagnosticsHtml('ru')).toContain('Состояние системы');
  });

  it('translates EVENT STREAM to ПОТОК СОБЫТИЙ', () => {
    expect(diagnosticsHtml('en')).toContain('EVENT STREAM');
    expect(diagnosticsHtml('ru')).toContain('ПОТОК СОБЫТИЙ');
  });

  it('localizes the empty event state', () => {
    expect(diagnosticsHtml('ru')).toContain('Проверенные события пока не получены.');
    expect(diagnosticsHtml('en')).toContain('No validated events received.');
  });

  it('localizes the policy decision label', () => {
    expect(diagnosticsHtml('ru')).toContain('РЕШЕНИЕ ПОЛИТИКИ');
    expect(diagnosticsHtml('en')).toContain('POLICY DECISION');
  });

  it('localizes the not-evaluated policy status', () => {
    expect(diagnosticsHtml('ru')).toContain('Не оценивалось');
    expect(diagnosticsHtml('en')).toContain('Not evaluated');
  });

  it('localizes Binding required for display only', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Binding required' }));
    expect(diagnosticsHtml('ru')).toContain('Требуется подключение модели');
    expect(get(modelGatewayStore).status).toBe('Binding required');
  });

  it('localizes Off for display only', () => {
    expect(get(modelGatewayStore).persistence).toBe('Off');
    expect(diagnosticsHtml('ru')).toContain('Хранение данных');
    expect(diagnosticsHtml('ru')).not.toContain('>Off<');
    expect(get(modelGatewayStore).persistence).toBe('Off');
  });

  it('localizes Unavailable for display only', () => {
    modelGatewayStore.update((state) => ({ ...state, status: 'Unavailable' }));
    expect(diagnosticsHtml('ru')).toContain('Недоступно');
    expect(get(modelGatewayStore).status).toBe('Unavailable');
  });

  it('keeps every reachable gateway runtime value unchanged internally', () => {
    const statuses = [
      'Not configured', 'Probing', 'Unavailable', 'Ready', 'Binding required', 'Bound',
      'Generating', 'Cancelling', 'Completed', 'Cancelled', 'Failed'
    ] as const;
    for (const status of statuses) {
      modelGatewayStore.update((state) => ({ ...state, status }));
      diagnosticsHtml('ru');
      expect(get(modelGatewayStore).status).toBe(status);
    }
  });

  it('preserves technical identifiers and raw event fields', () => {
    setLocale('ru');
    const translate = get(t);
    for (const identifier of [
      'LocalComet', 'llama.cpp', 'openai-compatible-local', 'managed-llama-cpp',
      'minimal', 'native-localcomet', 'model.turn.started', 'v6.84.5.1'
    ]) {
      expect(translate(identifier)).toBe(identifier);
    }
  });

  it('preserves the selected Diagnostics tab across locale switches', () => {
    setActiveInspectorSection('Телеметрия');
    setLocale('en');
    setLocale('ru');
    expect(get(activeInspectorSection)).toBe('Телеметрия');
  });

  it('does not reset Control Plane state on locale switch', () => {
    controlPlaneStore.update((state) => ({ ...state, bridgeState: 'ERROR' }));
    setLocale('en');
    setLocale('ru');
    expect(get(controlPlaneStore).bridgeState).toBe('ERROR');
  });

  it('does not reset Sidecar state on locale switch', () => {
    controlPlaneStore.update((state) => ({
      ...state,
      bootstrap: { sidecar_ready: true } as typeof state.bootstrap
    }));
    setLocale('en');
    setLocale('ru');
    expect(get(controlPlaneStore).bootstrap?.sidecar_ready).toBe(true);
  });

  it('keeps the event count unchanged on locale switch', () => {
    controlPlaneStore.update((state) => ({ ...state, eventCount: 7 }));
    setLocale('en');
    setLocale('ru');
    expect(get(controlPlaneStore).eventCount).toBe(7);
  });

  it('does not invent Ready or Connected state', () => {
    const html = diagnosticsHtml('en');
    expect(get(controlPlaneStore).bridgeState).toBe('DISCONNECTED');
    expect(get(controlPlaneStore).bootstrap).toBeNull();
    expect(html).not.toContain('Control Plane: Connected');
    expect(html).not.toContain('Sidecar: Ready');
  });

  it('keeps Diagnostics open while language changes', () => {
    inspectorVisible.set(true);
    setActiveInspectorSection('События');
    setLocale('en');
    expect(get(inspectorVisible)).toBe(true);
    expect(get(activeInspectorSection)).toBe('События');
    setLocale('ru');
    expect(get(inspectorVisible)).toBe(true);
    expect(get(activeInspectorSection)).toBe('События');
  });

  it('provides the required standalone Runtime and Connected translations', () => {
    setLocale('ru');
    expect(get(t)('diag.runtime')).toBe('Среда выполнения');
    expect(get(t)('diag.connected')).toBe('Подключено');
    setLocale('en');
    expect(get(t)('diag.runtime')).toBe('Runtime');
    expect(get(t)('diag.connected')).toBe('Connected');
  });
});
