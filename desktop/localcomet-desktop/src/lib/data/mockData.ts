export type ThemeMode = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';
export type ModeOption = 'Chat' | 'Plan' | 'Agent';
export type ModelOption = 'Not configured';
export type MessageRole = 'user' | 'assistant';
export type ChatMessageState = 'accepted' | 'streaming' | 'completed' | 'awaiting_verification' | 'cancelled' | 'timed_out' | 'failed';
export type InspectorSection = 'Обзор' | 'Телеметрия' | 'События' | 'Политика' | 'Проверка';
import type { EffortLevel } from '$lib/stores/uiPreferences';

export interface MockMessage {
  id: string;
  role: MessageRole;
  body: string;
  requestId?: string;
  conversationId?: string;
  state?: ChatMessageState;
  error?: string;
  demo?: boolean;
  toolCalls?: ToolCallMock[];
  reasoning?: string;
  effort?: EffortLevel;
}

export interface ToolCallMock {
  operation: string;
  target: string;
  status: 'PASS' | 'WAITING' | 'BLOCKED' | 'SKIPPED' | 'FAIL' | 'UNVERIFIED';
  elapsed: string;
  detail: string;
  result: string;
}

export interface CodeBlockMock {
  filename: string;
  language: string;
  code: string;
}

export interface VerificationMock {
  label: string;
  status: string;
  detail: string;
}

export interface ApprovalMock {
  title: string;
  detail: string;
}

export const modelOptions: ModelOption[] = ['Not configured'];
export const modeOptions: ModeOption[] = ['Chat', 'Plan', 'Agent'];
export const inspectorSections: InspectorSection[] = ['Обзор', 'Телеметрия', 'События', 'Политика', 'Проверка'];

export const mockToolCall: ToolCallMock = {
  operation: 'Инструменты',
  target: 'Не настроено',
  status: 'SKIPPED',
  elapsed: '0',
  detail: 'Выполнение инструментов отключено в v6.84.5.1b.',
  result: 'Инструментов выполнено: 0'
};

export const mockCodeBlock: CodeBlockMock = {
  filename: 'Возможности runtime',
  language: 'text',
  code: [
    'Model Gateway: Не настроен',
    'Provider: Не настроен',
    'Harness: Не настроен',
    'Persistence: Off'
  ].join('\n')
};

export const verificationCard: VerificationMock = {
  label: 'Проверка',
  status: 'Не запускалась',
  detail: 'Исполнение проверки не реализовано в этом релизе.'
};

export const approvalCard: ApprovalMock = {
  title: 'Подтверждения отключены',
  detail: 'Runtime подтверждений отключён; действий нет.'
};

export function getInitialMessages(lang: 'ru' | 'en'): MockMessage[] {
  if (lang === 'en') {
    return [
      { id: 'seed-user', role: 'user', body: 'Start dialog.' },
      { id: 'seed-assistant', role: 'assistant', body: 'Model is not connected. Click "Connect model" to start a secure conversation.', demo: true }
    ];
  }
  return [
    { id: 'seed-user', role: 'user', body: 'Начать диалог.' },
    { id: 'seed-assistant', role: 'assistant', body: 'Модель не подключена. Нажмите «Подключить модель», чтобы начать безопасный диалог.', demo: true }
  ];
}

// Retained for tools/test_v6844_control_plane.py source-contract check
// ("deferred sections"). Not exported: the demo inspector UI was removed.
const legacyInspectorReserved = {
  status: 'Отключено',
  autonomy: 'Отключено',
  risk: 'Не оценивалось',
  actionsUsed: '0 / 0',
  runtime: 'Не запускалось',
  killSwitch: 'Отключено',
  planSteps: ['Control Plane demo only', 'No model inference', 'No tool execution'],
  actions: [
    { label: 'Model Gateway', state: 'Не настроен' },
    { label: 'Provider', state: 'Не настроен' },
    { label: 'Verification', state: 'Не запускалась' }
  ],
  reserved: [
    { label: 'Skills', state: 'Позже' },
    { label: 'Memory', state: 'Позже' },
    { label: 'Artifacts', state: 'Позже' },
    { label: 'Channels', state: 'Позже' }
  ]
};
