import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import KnowledgeToggle from '../src/lib/components/knowledge/KnowledgeToggle.svelte';
import ConversationSidebar from '../src/lib/components/shell/ConversationSidebar.svelte';

import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import { setLocale } from '../src/lib/i18n';
import { resetShellStores } from '../src/lib/stores/shellStore';

const sourceModules = import.meta.glob('../src/**/*.{css,svelte,ts}', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;

function source(relativePath: string): string {
  const content = sourceModules[relativePath];
  if (typeof content !== 'string') throw new Error('Source fixture not found: ' + relativePath);
  return content;
}

function visibleButtonBlocks(relativePath: string): readonly string[] {
  return source(relativePath).match(/<button\b[\s\S]*?<\/button>/g) ?? [];
}

beforeEach(() => {
  resetShellStores();
  setLocale('ru');
});

describe('UP02-WP01-HF2 visible production controls', () => {
  it('uses a recognizable local gear while preserving settings semantics', () => {
    const icon = source('../src/lib/components/common/Icon.svelte');
    const rail = render(ConversationSidebar).body;
    expect(icon).toContain('M12.22 2h-.44');
    expect(icon).toContain('<circle cx="12" cy="12" r="3"/>');
    expect(rail).toContain('aria-label="Настройки"');
    expect(rail).toContain('title="Настройки"');
    expect(rail).toContain('data-settings-trigger="true"');
  });

  it('keeps only the real local chat and useful pinned identity', () => {
    const html = render(ConversationSidebar).body;
    expect(html).toContain('Новый чат');
    expect(html).toContain('aria-current="page"');
    for (const removed of ['Демо отмены', 'Позже', 'v6.84.5.1b', 'Frontend', 'Русский UX']) {
      expect(html).not.toContain(removed);
    }
  });

  it('localizes header icon actions and avoids the desktop duplicate sidebar control', () => {
    const header = source('../src/lib/components/shell/ChatHeader.svelte');
    expect(header).toContain("aria-label={$t('sidebar.toggle')}");
    expect(header).toContain("aria-label={$t('diag.toggle')}");
    expect(header).toMatch(/\.sidebar-toggle\s*\{\s*display:\s*none;/s);
    expect(header).toMatch(/@media \(max-width: 920px\)[\s\S]*\.sidebar-toggle\s*\{\s*display:\s*grid;/s);
  });

  it('keeps version and build in About but removes redundant shell and sidebar badges', () => {
    const shell = source('../src/lib/components/shell/AppShell.svelte');
    const sidebar = source('../src/lib/components/shell/ConversationSidebar.svelte');
    const about = render(SettingsPanel).body;
    expect(shell).not.toContain('title-version');
    expect(sidebar).not.toContain('projectLabels');
    expect(about).toContain('Версия');
    expect(about).toContain('Сборка');
  });

  it('gates Project Knowledge without a switch, preview request, or memory claim', () => {
    const ru = render(KnowledgeToggle).body;
    const composer = source('../src/lib/components/chat/MessageComposer.svelte');
    expect(ru).toContain('Контекст проекта пока недоступен');
    expect(ru).not.toContain('<button');
    expect(composer).not.toContain('prepareProjectKnowledge');
    expect(composer).not.toContain('createPendingKnowledgeTurn');
    expect(composer).not.toContain('KnowledgePreviewPanel');
    expect(composer).toContain('startLocalModelTurn(draft, $selectedConversationId, $includedFileIds)');
  });

  it('renders the exact English unavailable knowledge state', () => {
    setLocale('en');
    const html = render(KnowledgeToggle).body;
    expect(html).toContain('Project context is currently unavailable');
  });

  it('removes normal-chat debug and unavailable placeholder buttons', () => {
    const composer = render(MessageComposer).body;
    const modelDrawer = source('../src/lib/components/model/ModelSetupDrawer.svelte');
    expect(composer).not.toContain('Tools (not yet available)');
    expect(composer).not.toContain('Инструменты (пока недоступны)');
    expect(composer).not.toContain('request-metrics');
    expect(modelDrawer).not.toContain('class="secondary-button" disabled');
  });

  it('keeps Diagnostics useful and removes demo, policy, verification, and no-op tab controls', () => {
    const html = render(Diagnostics).body;
    expect(html).toContain('Состояние системы');
    expect(html).toContain('Шлюз модели');
    expect(html).not.toContain('Запустить демо');
    expect(html).not.toContain('Отменить демо');
    expect(html).not.toContain('role="tablist"');
    expect(html).not.toContain('Решение политики');
  });

  it('gives every remaining production button in affected surfaces a real handler', () => {
    const files = [
      '../src/lib/components/shell/ConversationSidebar.svelte',
      '../src/lib/components/shell/ChatHeader.svelte',
      '../src/lib/components/chat/MessageComposer.svelte',
      '../src/lib/components/chat/MessageList.svelte',
      '../src/lib/components/shell/SettingsPanel.svelte',
      '../src/lib/components/agent/Diagnostics.svelte',
      '../src/lib/components/model/ModelSetupDrawer.svelte',
      '../src/lib/components/model/ModelManagerSection.svelte'
    ];
    const buttons = files.flatMap(visibleButtonBlocks);
    expect(buttons.length).toBeGreaterThan(0);
    for (const button of buttons) {
      expect(button, button.slice(0, 120)).toContain('onclick=');
      expect(button).toMatch(/aria-label=|<span>|>\{\$t\(|>\s*\{\$t\(/);
    }
  });
});
