import { get, writable } from 'svelte/store';
import { getInitialMessages, inspectorSections, modeOptions, modelOptions } from '$lib/data/mockData';
import type { InspectorSection, MockMessage, ModeOption, ModelOption, ThemeMode } from '$lib/data/mockData';
import { locale } from '$lib/i18n';

export const MAX_DRAFT_LENGTH = 1200;

export type WorkspaceMode = 'chat' | 'review';

const DEFAULT_CONVERSATION = 'control-plane-demo';
let messageCounter = 0;

function cloneMessages(): MockMessage[] {
  return getInitialMessages(get(locale)).map((message) => ({ ...message }));
}

export const themeMode = writable<ThemeMode>('system');
export const activeWorkspace = writable<WorkspaceMode>('chat');
export const sidebarExpanded = writable(true);
export const inspectorVisible = writable(false);
export const inspectorDrawerOpen = writable(false);
export const selectedConversationId = writable(DEFAULT_CONVERSATION);
export const selectedModel = writable<ModelOption>(modelOptions[0]);
export const selectedMode = writable<ModeOption>('Chat');
export const mockMessages = writable<MockMessage[]>(cloneMessages());
export const composerDraft = writable('');
export const activeInspectorSection = writable<InspectorSection>(inspectorSections[0]);
export const toolsPopoverOpen = writable(false);

export type ModelSetupMode = 'external' | 'managed';
export const modelSetupDrawerOpen = writable(false);
export const modelSetupMode = writable<ModelSetupMode>('external');
export const modelConnected = writable(false);

export function setActiveWorkspace(workspace: WorkspaceMode): void {
  activeWorkspace.set(workspace);
  closePopovers();
}

export function setThemeMode(mode: ThemeMode): void {
  themeMode.set(mode);
}

export function setSelectedModel(model: ModelOption): void {
  if (modelOptions.includes(model)) selectedModel.set(model);
}

export function setSelectedMode(mode: ModeOption): void {
  if (modeOptions.includes(mode)) selectedMode.set(mode);
}

export function setSelectedConversation(id: string): void {
  selectedConversationId.set(id);
}

export function setComposerDraft(value: string): void {
  composerDraft.set(value.slice(0, MAX_DRAFT_LENGTH));
}

export function appendMockMessage(rawDraft: string): boolean {
  const bounded = rawDraft.slice(0, MAX_DRAFT_LENGTH);
  const body = bounded.trim();
  if (!body) return false;

  messageCounter += 1;
  mockMessages.update((messages) => [
    ...messages,
    {
      id: `mock-user-${messageCounter}`,
      role: 'user',
      body
    }
  ]);
  composerDraft.set('');
  return true;
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
  inspectorDrawerOpen.set(false);
  modelSetupDrawerOpen.set(false);
}

export function handleGlobalEscape(key: string): boolean {
  if (key !== 'Escape') return false;
  closePopovers();
  return true;
}

export function resetShellStores(): void {
  messageCounter = 0;
  themeMode.set('system');
  activeWorkspace.set('chat');
  sidebarExpanded.set(true);
  inspectorVisible.set(false);
  inspectorDrawerOpen.set(false);
  selectedConversationId.set(DEFAULT_CONVERSATION);
  selectedModel.set(modelOptions[0]);
  selectedMode.set('Chat');
  mockMessages.set(cloneMessages());
  composerDraft.set('');
  activeInspectorSection.set(inspectorSections[0]);
  toolsPopoverOpen.set(false);
  modelSetupDrawerOpen.set(false);
  modelSetupMode.set('external');
  modelConnected.set(false);
}