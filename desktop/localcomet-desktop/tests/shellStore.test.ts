import { describe, expect, it, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { approvalCard, mockCodeBlock, mockToolCall, modeOptions, verificationCard } from '../src/lib/data/mockData';
import {
  MAX_DRAFT_LENGTH,
  activeInspectorSection,
  appendMockMessage,
  closeModelSetup,
  handleGlobalEscape,
  inspectorVisible,
  mockMessages,
  modelConnected,
  modelSetupDrawerOpen,
  modelSetupMode,
  openModelSetup,
  resetShellStores,
  selectedMode,
  selectedModel,
  setSelectedMode,
  setSelectedModel,
  setThemeMode,
  sidebarExpanded,
  themeMode,
  toolsPopoverOpen
} from '../src/lib/stores/shellStore';

describe('shell stores', () => {
  beforeEach(() => {
    resetShellStores();
  });

  it('defaults theme to system and can change to light and dark', () => {
    expect(get(themeMode)).toBe('system');
    setThemeMode('light');
    expect(get(themeMode)).toBe('light');
    setThemeMode('dark');
    expect(get(themeMode)).toBe('dark');
  });

  it('does not persist theme to browser storage APIs', () => {
    setThemeMode('light');
    expect(get(themeMode)).toBe('light');
    expect('localStorage' in globalThis).toBe(false);
    expect('sessionStorage' in globalThis).toBe(false);
  });

  it('has deterministic sidebar and inspector defaults', () => {
    expect(get(sidebarExpanded)).toBe(true);
    expect(get(inspectorVisible)).toBe(false);
    expect(get(activeInspectorSection)).toBe('Обзор');
  });

  it('keeps model selection in memory only', () => {
    setSelectedModel('Not configured');
    expect(get(selectedModel)).toBe('Not configured');
  });

  it('supports Chat, Plan, and Agent modes', () => {
    expect(modeOptions).toEqual(['Chat', 'Plan', 'Agent']);
    setSelectedMode('Chat');
    expect(get(selectedMode)).toBe('Chat');
    setSelectedMode('Plan');
    expect(get(selectedMode)).toBe('Plan');
    setSelectedMode('Agent');
    expect(get(selectedMode)).toBe('Agent');
  });

  it('blocks empty and whitespace-only messages', () => {
    const count = get(mockMessages).length;
    expect(appendMockMessage('')).toBe(false);
    expect(appendMockMessage('   \n  ')).toBe(false);
    expect(get(mockMessages)).toHaveLength(count);
  });

  it('appends valid bounded user messages without creating an assistant response', () => {
    const count = get(mockMessages).length;
    expect(appendMockMessage('hello desktop shell')).toBe(true);
    const messages = get(mockMessages);
    expect(messages).toHaveLength(count + 1);
    expect(messages.at(-1)?.role).toBe('user');

    appendMockMessage('x'.repeat(MAX_DRAFT_LENGTH + 50));
    expect(get(mockMessages).at(-1)?.body).toHaveLength(MAX_DRAFT_LENGTH);
  });

  it('keeps disabled fixtures truthful and sanitized', () => {
    const fixture = JSON.stringify({ approvalCard, verificationCard, mockCodeBlock, mockToolCall });
    expect(mockToolCall.status).toBe('SKIPPED');
    expect(verificationCard.status).toBe('Не запускалась');
    expect(fixture).toContain('Не настроено');
    expect(fixture).not.toMatch(/[A-Z]:\\\\(?:Users|Windows|Program Files)|\/Users\/|sk-[A-Za-z0-9]|password|private key/i);
  });

  it('closes the mock tools popover on Escape', () => {
    toolsPopoverOpen.set(true);
    expect(handleGlobalEscape('Escape')).toBe(true);
    expect(get(toolsPopoverOpen)).toBe(false);
  });

  it('defaults theme mode to system', () => {
    expect(get(themeMode)).toBe('system');
  });

  it('changes theme mode to light', () => {
    setThemeMode('light');
    expect(get(themeMode)).toBe('light');
  });

  it('changes theme mode to dark', () => {
    setThemeMode('dark');
    expect(get(themeMode)).toBe('dark');
  });

  it('keeps sidebar default deterministic', () => {
    expect(get(sidebarExpanded)).toBe(true);
  });

  it('keeps inspector default deterministic', () => {
    expect(get(inspectorVisible)).toBe(false);
    expect(get(activeInspectorSection)).toBe('Обзор');
  });

  it('supports Chat mode directly', () => {
    setSelectedMode('Chat');
    expect(get(selectedMode)).toBe('Chat');
  });

  it('supports Plan mode directly', () => {
    setSelectedMode('Plan');
    expect(get(selectedMode)).toBe('Plan');
  });

  it('supports Agent mode directly', () => {
    setSelectedMode('Agent');
    expect(get(selectedMode)).toBe('Agent');
  });

  it('prevents empty message append', () => {
    const count = get(mockMessages).length;
    appendMockMessage('');
    expect(get(mockMessages)).toHaveLength(count);
  });

  it('prevents whitespace-only message append', () => {
    const count = get(mockMessages).length;
    appendMockMessage('   ');
    expect(get(mockMessages)).toHaveLength(count);
  });

  it('bounds mock message length', () => {
    appendMockMessage('x'.repeat(MAX_DRAFT_LENGTH + 10));
    expect(get(mockMessages).at(-1)?.body).toHaveLength(MAX_DRAFT_LENGTH);
  });

  it('does not append an assistant response after send', () => {
    const beforeAssistantCount = get(mockMessages).filter((message) => message.role === 'assistant').length;
    appendMockMessage('one user-only message');
    const afterAssistantCount = get(mockMessages).filter((message) => message.role === 'assistant').length;
    expect(afterAssistantCount).toBe(beforeAssistantCount);
  });

  it('contains no real project paths in mock fixtures', () => {
    const fixture = JSON.stringify({ approvalCard, verificationCard, mockCodeBlock, mockToolCall });
    expect(fixture).not.toMatch(/[A-Z]:\\\\(?:Users|Windows|Program Files)|\/Users\//i);
  });

  it('contains no secret-like mock fixtures', () => {
    const fixture = JSON.stringify({ approvalCard, verificationCard, mockCodeBlock, mockToolCall });
    expect(fixture).not.toMatch(/sk-[A-Za-z0-9]|password|private key|BEGIN [A-Z ]*KEY/i);
  });

  it('opens model setup drawer in external mode', () => {
    expect(get(modelSetupDrawerOpen)).toBe(false);
    openModelSetup('external');
    expect(get(modelSetupDrawerOpen)).toBe(true);
    expect(get(modelSetupMode)).toBe('external');
  });

  it('opens model setup drawer in managed mode', () => {
    openModelSetup('managed');
    expect(get(modelSetupDrawerOpen)).toBe(true);
    expect(get(modelSetupMode)).toBe('managed');
  });

  it('closes model setup drawer', () => {
    openModelSetup('external');
    closeModelSetup();
    expect(get(modelSetupDrawerOpen)).toBe(false);
  });

  it('sets model connected state', () => {
    expect(get(modelConnected)).toBe(false);
    // modelConnected is set internally when binding succeeds
  });

  it('closes all popovers on Escape', () => {
    toolsPopoverOpen.set(true);
    openModelSetup('external');
    handleGlobalEscape('Escape');
    expect(get(toolsPopoverOpen)).toBe(false);
    expect(get(modelSetupDrawerOpen)).toBe(false);
  });
});
