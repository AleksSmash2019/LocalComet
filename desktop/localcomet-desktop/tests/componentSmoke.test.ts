import { render } from 'svelte/server';
import { describe, expect, it, beforeEach } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import ApprovalCard from '../src/lib/components/chat/ApprovalCard.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import ConversationSidebar from '../src/lib/components/shell/ConversationSidebar.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';

import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import ToolCallCard from '../src/lib/components/chat/ToolCallCard.svelte';
import { mockToolCall } from '../src/lib/data/mockData';
import { resetShellStores } from '../src/lib/stores/shellStore';
import { requestApprovalForTool, resetApprovalStore } from '../src/lib/stores/approvalStore';

describe('component smoke tests', () => {
  beforeEach(() => {
    resetShellStores();
    resetApprovalStore();
  });

  it('renders all structural components without crashing', () => {
    // AppShell component is not imported, so we will skip it here if it's not defined
    expect(() => render(ChatHeader)).not.toThrow();
    expect(() => render(ConversationSidebar)).not.toThrow();
  });

  it('renders functional sessions without placeholder or preference clutter', () => {
    const html = render(ConversationSidebar).body;
    expect(html).not.toContain('Зарезервировано');
    expect(html).not.toContain('Документы');
    expect(html).not.toContain('Новый тред');
    expect(html).not.toContain('Демо отмены');
    expect(html).not.toContain('v6.84.5.1b');
    expect(html).not.toContain('Frontend');
    expect(html).not.toContain('Использовать системную тему');
    expect(html).toContain('aria-expanded="true"');
  });

  it('renders the chat header without the removed Think and connect controls', () => {
    const html = render(ChatHeader).body;
    // The connect action moved next to the composer; "Think" was a no-op.
    expect(html).not.toContain('Think');
    expect(html).not.toContain('Настроить локальный AI');
  });

  it('keeps the composer free of duplicate connect controls', () => {
    // The empty-state card is the single place offering model setup.
    const html = render(MessageComposer).body;
    expect(html).not.toContain('connect-model-button');
    expect(html).not.toContain('Настроить локальный AI');
  });

  it('renders the tool card with sanitized target', () => {
    const html = render(ToolCallCard, { props: { tool: mockToolCall } }).body;
    expect(html).toContain('Инструменты');
    expect(html).toContain('Не настроено');
    expect(html).toContain('SKIPPED');
  });

  it('renders the approval card empty state when nothing is pending', () => {
    const html = render(ApprovalCard).body;
    expect(html).toContain('Нет запросов на подтверждение');
    expect(html).not.toContain('Подтвердить');
  });

  it('renders useful Diagnostics without demo controls or no-op tabs', () => {
    const html = render(Diagnostics).body;
    expect(html).toContain('Провайдер');
    expect(html).toContain('Не настроено');
    expect(html).not.toContain('Запустить демо');
    expect(html).not.toContain('role="tablist"');
  });

  it('renders composer with an associated accessible label', () => {
    const html = render(MessageComposer).body;
    expect(html).toContain('for="composer-draft"');
    expect(html).toContain('id="composer-draft"');
    expect(html).toContain('aria-label="Введите сообщение…"');
    expect(html).toContain('Контекст проекта пока недоступен');
    expect(html).not.toContain('Инструменты (пока недоступны)');
    expect(html).not.toContain('request-metrics');
  });

  it('renders enabled approval actions for a pending tool call', () => {
    requestApprovalForTool('files.write', { path: 'a.txt' });
    const html = render(ApprovalCard).body;
    expect(html).toContain('Подтверждение действия');
    expect(html).toContain('files.write');
    expect(html).toContain('Подтвердить');
    expect(html).toContain('Отклонить');
  });

  it('keeps theme controls accessible in Settings', () => {
    const html = render(SettingsPanel).body;
    expect(html).toContain('aria-label="Системная"');
    expect(html).toContain('title="Светлая"');
    expect(html).toContain('title="Тёмная"');
  });
});
