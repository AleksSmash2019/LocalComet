import { derived, get, writable } from 'svelte/store';
import { inspectorSections, modeOptions, modelOptions } from '$lib/data/mockData';
import type { ChatMessageState, InspectorSection, MockMessage, ModeOption, ModelOption, ThemeMode } from '$lib/data/mockData';
import { loadUiPreferences, updateUiPreferences } from './uiPreferences';
import { conversationStore, getActiveConversationId, resetConversationStore, selectConversation as selectConversationInStore } from './conversationStore';

export const MAX_DRAFT_LENGTH = 1200;
export const MAX_ASSISTANT_MESSAGE_LENGTH = 262_144;

export type WorkspaceMode = 'chat' | 'review' | 'setup';
export type SettingsSection = 'interface' | 'models' | 'observability' | 'about';

let messageCounter = 0;
const initialUiPreferences = loadUiPreferences();

function cloneMessages(): MockMessage[] {
  return [];
}

export const themeMode = writable<ThemeMode>(initialUiPreferences.theme);
export const activeWorkspace = writable<WorkspaceMode>('chat');
export const sidebarExpanded = writable(true);
export const inspectorVisible = writable(initialUiPreferences.diagnosticsPanel === 'open');
export const inspectorDrawerOpen = writable(initialUiPreferences.diagnosticsPanel === 'open');
export const settingsPanelOpen = writable(false);
export const settingsSection = writable<SettingsSection>('interface');
export const selectedConversationId = derived(conversationStore, ($state) => $state.activeId);
export const selectedModel = writable<ModelOption>(modelOptions[0]);
export const selectedMode = writable<ModeOption>('Chat');
export const chatMessages = writable<MockMessage[]>(cloneMessages());
export const mockMessages = chatMessages;
export const composerDraft = writable('');
export const activeInspectorSection = writable<InspectorSection>(inspectorSections[0]);
export const toolsPopoverOpen = writable(false);
export const commandPaletteOpen = writable(false);

export type ModelSetupMode = 'external' | 'managed';
export const modelSetupDrawerOpen = writable(false);
export const modelSetupMode = writable<ModelSetupMode>('external');
export const modelConnected = writable(false);

export function setActiveWorkspace(workspace: WorkspaceMode): void {
  activeWorkspace.set(workspace);
  toolsPopoverOpen.set(false);
  closeCommandPalette();
  closeSettings();
  modelSetupDrawerOpen.set(false);
}

export function setThemeMode(mode: ThemeMode): void {
  if (mode !== 'system' && mode !== 'light' && mode !== 'dark') return;
  themeMode.set(mode);
  updateUiPreferences({ theme: mode });
}

export function openSettings(sectionOrEvent: SettingsSection | Event = 'interface'): void {
  const section = typeof sectionOrEvent === 'string' ? sectionOrEvent : 'interface';
  toolsPopoverOpen.set(false);
  modelSetupDrawerOpen.set(false);
  settingsSection.set(section);
  settingsPanelOpen.set(true);
}

export function closeSettings(): void {
  settingsPanelOpen.set(false);
  settingsSection.set('interface');
}

export function openCommandPalette(): void {
  commandPaletteOpen.set(true);
}

export function closeCommandPalette(): void {
  commandPaletteOpen.set(false);
}

export function setDiagnosticsPanelOpen(open: boolean): void {
  if (typeof open !== 'boolean') return;
  inspectorVisible.set(open);
  inspectorDrawerOpen.set(open);
  updateUiPreferences({ diagnosticsPanel: open ? 'open' : 'closed' });
}

export function closeDiagnosticsPanel(): void {
  setDiagnosticsPanelOpen(false);
}

export function setSelectedModel(model: ModelOption): void {
  if (modelOptions.includes(model)) selectedModel.set(model);
}

export function setSelectedMode(mode: ModeOption): void {
  if (modeOptions.includes(mode)) selectedMode.set(mode);
}

export function setSelectedConversation(id: string): void {
  selectConversationInStore(id);
}

export function setComposerDraft(value: string): void {
  composerDraft.set(value.slice(0, MAX_DRAFT_LENGTH));
}

export function appendMockMessage(rawDraft: string): boolean {
  const bounded = rawDraft.slice(0, MAX_DRAFT_LENGTH);
  const body = bounded.trim();
  if (!body) return false;

  messageCounter += 1;
  const conversationId = getActiveConversationId();
  mockMessages.update((messages) => [
    ...messages,
    {
      id: `mock-user-${messageCounter}`,
      role: 'user',
      body,
      conversationId
    }
  ]);
  composerDraft.set('');
  return true;
}

export function appendAcceptedChatTurn(requestId: string, rawDraft: string, conversationId?: string): boolean {
  const bounded = rawDraft.slice(0, MAX_DRAFT_LENGTH);
  const body = bounded.trim();
  if (!body || !/^[0-9a-f]{24}$/.test(requestId)) return false;
  if (get(chatMessages).some((message) => message.requestId === requestId)) return false;

  messageCounter += 1;
  chatMessages.update((messages) => [
    ...messages,
    {
      id: `chat-user-${messageCounter}`,
      role: 'user',
      body,
      requestId,
      conversationId
    },
    {
      id: `chat-assistant-${messageCounter}`,
      role: 'assistant',
      body: '',
      requestId,
      conversationId,
      state: 'accepted'
    }
  ]);
  composerDraft.set('');
  return true;
}

export function appendAssistantChunk(requestId: string, chunk: string): boolean {
  if (!chunk || !/^[0-9a-f]{24}$/.test(requestId)) return false;
  let appended = false;
  chatMessages.update((messages) => messages.map((message) => {
    if (message.role !== 'assistant' || message.requestId !== requestId || isTerminalMessage(message.state)) return message;
    appended = true;
    return {
      ...message,
      body: `${message.body}${chunk}`.slice(0, MAX_ASSISTANT_MESSAGE_LENGTH),
      state: 'streaming'
    };
  }));
  return appended;
}

export function finalizeAssistantMessage(
  requestId: string,
  state: Exclude<ChatMessageState, 'accepted' | 'streaming'>,
  error?: string
): boolean {
  let finalized = false;
  chatMessages.update((messages) => messages.map((message) => {
    if (message.role !== 'assistant' || message.requestId !== requestId || isTerminalMessage(message.state)) return message;
    finalized = true;
    return { ...message, state, error: error?.slice(0, 240) };
  }));
  return finalized;
}

function isTerminalMessage(state: ChatMessageState | undefined): boolean {
  return state === 'completed' || state === 'cancelled' || state === 'timed_out' || state === 'failed';
}

export function sendComposerDraft(): boolean {
  return appendMockMessage(get(composerDraft));
}

export function setActiveInspectorSection(section: InspectorSection): void {
  if (inspectorSections.includes(section)) activeInspectorSection.set(section);
}

export function openModelSetup(mode: ModelSetupMode = 'external'): void {
  modelSetupMode.set(mode);
  modelSetupDrawerOpen.set(true);
}

export function closeModelSetup(): void {
  modelSetupDrawerOpen.set(false);
}

export function setModelConnected(connected: boolean): void {
  modelConnected.set(connected);
}

export function closePopovers(): void {
  toolsPopoverOpen.set(false);
  closeCommandPalette();
  closeSettings();
  if (get(inspectorVisible) || get(inspectorDrawerOpen)) closeDiagnosticsPanel();
  modelSetupDrawerOpen.set(false);
}

export function handleGlobalEscape(key: string): boolean {
  if (key !== 'Escape') return false;
  if (get(commandPaletteOpen)) {
    closeCommandPalette();
    return true;
  }
  const hadOpenSurface =
    get(settingsPanelOpen) ||
    get(toolsPopoverOpen) ||
    get(inspectorVisible) ||
    get(inspectorDrawerOpen) ||
    get(modelSetupDrawerOpen);
  if (!hadOpenSurface) return false;
  closePopovers();
  return true;
}

export function resetShellStores(): void {
  const preferences = loadUiPreferences();
  messageCounter = 0;
  themeMode.set(preferences.theme);
  activeWorkspace.set('chat');
  sidebarExpanded.set(true);
  inspectorVisible.set(preferences.diagnosticsPanel === 'open');
  inspectorDrawerOpen.set(preferences.diagnosticsPanel === 'open');
  settingsPanelOpen.set(false);
  settingsSection.set('interface');
  resetConversationStore();
  selectedModel.set(modelOptions[0]);
  selectedMode.set('Chat');
  mockMessages.set(cloneMessages());
  composerDraft.set('');
  activeInspectorSection.set(inspectorSections[0]);
  toolsPopoverOpen.set(false);
  commandPaletteOpen.set(false);
  modelSetupDrawerOpen.set(false);
  modelSetupMode.set('external');
  modelConnected.set(false);
}
