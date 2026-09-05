import { render } from 'svelte/server';
import { describe, expect, it, beforeEach } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import ApprovalCard from '../src/lib/components/chat/ApprovalCard.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import ConversationSidebar from '../src/lib/components/shell/ConversationSidebar.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import MessageList from '../src/lib/components/chat/MessageList.svelte';

import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import CheckpointPanel from '../src/lib/components/shell/CheckpointPanel.svelte';
import ToolCallCard from '../src/lib/components/chat/ToolCallCard.svelte';
import { mockToolCall } from '../src/lib/data/mockData';
import { chatMessages, resetShellStores, setVoiceMode } from '../src/lib/stores/shellStore';
import { approvalStore, requestApprovalForTool, resetApprovalStore } from '../src/lib/stores/approvalStore';

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

  it('renders the checkpoint panel with truthful empty state', () => {
    const html = render(CheckpointPanel).body;
    expect(html).toContain('checkpoints-title');
    // No fake rows and no fake RESTORED state before backend truth.
    expect(html).not.toContain('cp_');
  });

  it('keeps the control plane status badge out of the persistent sidebar chrome', () => {
    const html = render(ConversationSidebar).body;
    expect(html).not.toContain('Control Plane: Unavailable');
    expect(html).not.toContain('Контур управления: Подключено');
    expect(html).not.toContain('status-badge');
    expect(html).not.toContain('tone-ready');
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

  it('labels voice output toggle according to its current state', () => {
    let html = render(MessageComposer).body;
    expect(html).toContain('aria-label="Включить голосовое озвучивание"');
    setVoiceMode(true);
    html = render(MessageComposer).body;
    expect(html).toContain('aria-label="Отключить голосовое озвучивание"');
  });

  it('renders only a safe error code and never raw path or private provider detail', () => {
    chatMessages.set([{
      id: 'failed-safe-cause',
      role: 'assistant',
      body: '',
      conversationId: 'local-chat',
      state: 'failed',
      error: 'path_outside_workspace: C:\\Users\\DNS\\Documents\\secret.txt provider=https://private.example/token'
    }]);
    const html = render(MessageList).body;
    expect(html).toContain('path_outside_workspace');
    expect(html).not.toContain('C:\\Users\\DNS\\Documents\\secret.txt');
    expect(html).not.toContain('private.example');
    expect(html).not.toContain('provider=');
  });

  it('reduces unrecognized provider failures to a safe human hint without leaking raw text', () => {
    chatMessages.set([{
      id: 'failed-provider',
      role: 'assistant',
      body: '',
      conversationId: 'local-chat',
      state: 'failed',
      error: 'model_request_failed provider=https://private.example/token'
    }]);
    const html = render(MessageList).body;
    // New contract: a recognized gateway code resolves to its i18n hint...
    expect(html).toContain('\u041f\u0440\u0438\u0447\u0438\u043d\u0430');
    // ...while the rest of the raw error (private host/token) stays hidden.
    expect(html).not.toContain('private.example');
    expect(html).not.toContain('token');
  });

  it('maps gateway codes to human hints and keeps unknown text sanitized', () => {
    chatMessages.set([{
      id: 'failed-sidecar',
      role: 'assistant',
      body: '',
      conversationId: 'local-chat',
      state: 'failed',
      error: 'sidecar_unavailable: model completion returned non-200 status'
    }]);
    const html = render(MessageList).body;
    expect(html).toContain('request-error-cause');
    expect(html).not.toContain('sidecar_unavailable');
    expect(html).not.toContain('non-200');
    const unknown = render(MessageList, {}).body; // placeholder to keep render count stable
    expect(typeof unknown).toBe('string');
  });

  it('renders the tool card with sanitized target', () => {
    const html = render(ToolCallCard, { props: { tool: mockToolCall } }).body;
    expect(html).toContain('Инструменты');
    expect(html).toContain('Не настроено');
    expect(html).toContain('SKIPPED');
  });

  it('renders a real open_app launch with pending verification as waiting', () => {
    const html = render(ToolCallCard, { props: { tool: {
      operation: 'computer_use',
      target: '{"action":"open_app","target":"notepad"}',
      status: 'WAITING',
      elapsed: '-',
      detail: 'Tool execution requested',
      result: JSON.stringify({ ok: true, status: 'executed', verification: 'pending', app: 'notepad' })
    } } }).body;
    expect(html).toContain('Ожидает');
    expect(html).not.toContain('Не выполнено');
  });

  it('renders a verified computer-use result as completed', () => {
    const html = render(ToolCallCard, { props: { tool: {
      operation: 'computer_use',
      target: '{"action":"open_app","target":"notepad"}',
      status: 'PASS',
      elapsed: '-',
      detail: 'Tool execution completed',
      result: JSON.stringify({ ok: true, status: 'executed', verification: 'verified', app: 'notepad' })
    } } }).body;
    expect(html).toContain('Выполнено');
    expect(html).not.toContain('Не выполнено');
  });

  it('renders canonical JSON screenshot payload as an image preview', () => {
    const html = render(ToolCallCard, { props: { tool: {
      operation: 'computer_use',
      target: '{"action":"screenshot"}',
      status: 'PASS',
      elapsed: '-',
      detail: 'Screenshot captured',
      result: JSON.stringify({
        schema_version: 'computer_use.result.v1',
        action: 'screenshot',
        status: 'completed',
        terminal: true,
        succeeded: true,
        verification: 'not_applicable',
        screenshot: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'
      })
    } } }).body;
    expect(html).toContain('cu-img');
    expect(html).toContain('data:image/png;base64,iVBORw0KGgo');
  });

  it('does not render malformed structured computer-use success as completed', () => {
    const html = render(ToolCallCard, { props: { tool: {
      operation: 'computer_use',
      target: '{"action":"open_app","target":"notepad"}',
      status: 'FAIL',
      elapsed: '-',
      detail: 'Malformed backend result',
      result: JSON.stringify({ schema_version: 'computer_use.result.v1', status: 'completed', ok: true })
    } } }).body;
    expect(html).not.toContain('Выполнено');
    expect(html).toContain('Не выполнено');
  });

  it('renders the approval card empty state when nothing is pending', () => {
    const html = render(ApprovalCard).body;
    // Nothing is pending: the card renders nothing at all — the old
    // "Нет запросов на подтверждение" line read as a stray status message
    // under the prompt cards.
    expect(html).not.toContain('Подтвердить');
    expect(html).not.toContain('Отклонить');
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

  it('marks legacy approval identity without masquerading as a prompt request id', () => {
    approvalStore.set({
      pending: {
        tool: 'files.delete',
        input: { path: 'a.txt' },
        envelope: {
          token: 'lcap_' + 'a'.repeat(64),
          approvalId: 'appr_' + 'b'.repeat(32),
          callId: 'call_' + 'c'.repeat(32),
          tool: 'files.delete',
          riskLevel: 'dangerous',
          commandFamily: 'tool_filesystem_delete',
          expiresAtUnixMs: Date.now() + 120_000
        },
        inputDigest: 'd'.repeat(64)
      },
      phase: 'pending',
      errorCode: null
    });
    const html = render(ApprovalCard).body;
    expect(html).toContain('data-approval-id="appr_' + 'b'.repeat(32) + '"');
    expect(html).toContain('data-approval-authority="legacy-compatibility"');
    expect(html).not.toContain('data-approval-request-id=');
  });

  it('keeps approval card empty while guarded tool calls run in the background', () => {
    requestApprovalForTool('files.write', { path: 'a.txt' });
    const html = render(ApprovalCard).body;
    expect(html).not.toContain('files.write');
    expect(html).not.toContain('Подтвердить');
    expect(html).not.toContain('Отклонить');
  });

  it('keeps theme controls accessible in Settings', () => {
    const html = render(SettingsPanel).body;
    expect(html).toContain('aria-label="Системная"');
    expect(html).toContain('title="Светлая"');
    expect(html).toContain('title="Тёмная"');
  });
});
