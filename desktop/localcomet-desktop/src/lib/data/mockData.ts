export type ThemeMode = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';
export type ModeOption = 'Chat' | 'Plan' | 'Agent';
export type ModelOption = 'Not configured';
export type MessageRole = 'user' | 'assistant';
export type ChatMessageState = 'accepted' | 'streaming' | 'completed' | 'cancelled' | 'timed_out' | 'failed';
export type InspectorSection = 'Обзор' | 'Телеметрия' | 'События' | 'Политика' | 'Проверка';

export interface MockMessage {
  id: string;
  role: MessageRole;
  body: string;
  requestId?: string;
  state?: ChatMessageState;
  error?: string;
  demo?: boolean;
}

export interface ConversationItem {
  id: string;
  title: string;
  meta: string;
  selected?: boolean;
}

export interface ConversationGroup {
  label: string;
  items: ConversationItem[];
}

export interface ToolCallMock {
  operation: string;
  target: string;
  status: 'PASS' | 'WAITING' | 'SKIPPED';
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

export const conversationGroups: ConversationGroup[] = [
  {
    label: 'Локальные чаты',
    items: [
      { id: 'local-chat', title: 'Новый чат', meta: 'Модель не подключена', selected: true },
      { id: 'cancellation-demo', title: 'Демо отмены', meta: 'Требуется модель' }
    ]
  },
  {
    label: 'Зарезервировано',
    items: [{ id: 'audit-placeholder', title: 'Аудит', meta: 'Позже' }]
  },
  {
    label: 'Отключено',
    items: [{ id: 'documents', title: 'Документы', meta: 'Позже' }]
  }
];

export const pinnedProject = {
  title: 'LocalComet',
  detail: 'Локальный чат с моделью'
};

export const projectLabels = ['v6.84.5.1b', 'Frontend', 'Русский UX'];

export const legacyRegressionAnchors = {
  sanitizedPath: '<PROJECT_ROOT>/modules/example.py',
  deferred: ['Skills — Позже', 'Memory — Позже', 'Artifacts — Позже', 'Channels — Позже']
};

export const initialMessages: MockMessage[] = [
  {
    id: 'seed-user',
    role: 'user',
    body: 'Начать диалог.'
  },
  {
    id: 'seed-assistant',
    role: 'assistant',
    body: 'Модель не подключена. Нажмите «Подключить модель», чтобы начать безопасный диалог.',
    demo: true
  }
];

export const reasoningStatus = {
  title: 'Примечание',
  status: 'ДЕМО',
  detail: 'Этот релиз проверяет только Control Plane. Без подключённой модели ответов нет.'
};

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

export const inspectorMock = {
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

export function conversationTitleById(id: string): string {
  for (const group of conversationGroups) {
    const item = group.items.find((conversation) => conversation.id === id);
    if (item) return item.title;
  }
  return 'Новый чат';
}

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
