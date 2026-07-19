import { render } from 'svelte/server';
import { describe, expect, it, beforeEach } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import ApprovalCard from '../src/lib/components/chat/ApprovalCard.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import ConversationSidebar from '../src/lib/components/shell/ConversationSidebar.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import NavigationRail from '../src/lib/components/shell/NavigationRail.svelte';
import ToolCallCard from '../src/lib/components/chat/ToolCallCard.svelte';
import { approvalCard, mockToolCall } from '../src/lib/data/mockData';
import { resetShellStores } from '../src/lib/stores/shellStore';

describe('component smoke tests', () => {
  beforeEach(() => {
    resetShellStores();
  });

  it('renders the navigation rail with product modules', () => {
    const html = render(NavigationRail).body;
    expect(html).toContain('aria-label="Основная навигация"');
    expect(html).toContain('aria-label="Чат"');
    expect(html).toContain('Задачи — позже');
    expect(html).toContain('aria-current="page"');
  });

  it('renders grouped demo sessions and theme controls in the sidebar', () => {
    const html = render(ConversationSidebar).body;
    expect(html).toContain('LocalComet');
    expect(html).toContain('Зарезервировано');
    expect(html).toContain('Использовать системную тему');
    expect(html).toContain('aria-expanded="true"');
  });

  it('renders the chat header with truthful runtime labels', () => {
    const html = render(ChatHeader).body;
    expect(html).toContain('Не подключено');
    expect(html).toContain('Подключить модель');
  });

  it('renders the tool card with sanitized target', () => {
    const html = render(ToolCallCard, { props: { tool: mockToolCall } }).body;
    expect(html).toContain('Инструменты');
    expect(html).toContain('Не настроено');
    expect(html).toContain('SKIPPED');
  });

  it('renders the disconnected approval card with disabled actions', () => {
    const html = render(ApprovalCard, { props: { item: approvalCard } }).body;
    expect(html).toContain('Подтверждения отключены');
    expect(html).toContain('disabled');
    expect(html).toContain('Подтвердить');
    expect(html).toContain('Отклонить');
  });

  it('renders the Diagnostics with truthful disabled state', () => {
    const html = render(Diagnostics).body;
    expect(html).toContain('Провайдер');
    expect(html).toContain('Не настроено');
    expect(html).toContain('Подтверждение');
    expect(html).toContain('Отключено');
  });

  it('renders composer with an associated accessible label', () => {
    const html = render(MessageComposer).body;
    expect(html).toContain('for="composer-draft"');
    expect(html).toContain('id="composer-draft"');
    expect(html).toContain('aria-label="Введите сообщение…"');
  });

  it('marks disabled approval buttons semantically', () => {
    const html = render(ApprovalCard, { props: { item: approvalCard } }).body;
    expect(html.match(/disabled/g)?.length).toBeGreaterThanOrEqual(2);
  });

  it('keeps theme controls accessible in the sidebar', () => {
    const html = render(ConversationSidebar).body;
    expect(html).toContain('aria-label="Использовать системную тему"');
    expect(html).toContain('aria-label="Использовать светлую тему"');
    expect(html).toContain('aria-label="Использовать тёмную тему"');
  });
});
