# Карта Svelte-фронтенда

## Точки входа

`src/routes/+layout.ts` отключает SSR и включает prerender. Единственный route `src/routes/+page.svelte` рендерит `AppShell`. На mount `AppShell.svelte:149-160` инициализирует Control Plane, Model Gateway, acquisition и knowledge subscriptions; cleanup их останавливает/сбрасывает.

Production render tree (`AppShell.svelte:192-239`):

```text
+page
└─ AppShell
   ├─ NavigationRail
   ├─ chat: ConversationSidebar + ChatHeader + MessageList + MessageComposer
   │  ├─ FilesPanel -> FilePreviewDialog
   │  ├─ KnowledgeToggle (не KnowledgePreviewPanel)
   │  ├─ Diagnostics -> TelemetryRow/EventStream
   │  └─ ModelSetupDrawer (условно)
   ├─ review: ReviewCenterWorkspace -> queue/command/detail/decision/activity panels
   ├─ setup: OnboardingScreen
   ├─ SettingsPanel (overlay) -> ModelManagerSection / ObservabilityRoom
   └─ CommandPalette
```

## Все компоненты

| Компонент | Кто рендерит / дети | Stores и действия |
|---|---|---|
| `routes/+page.svelte` | route -> `AppShell` | нет |
| `shell/AppShell.svelte` | root; дети перечислены выше | читает shell, model, control plane; lifecycle stores; responsive `sidebarExpanded` |
| `shell/NavigationRail.svelte` | `AppShell`; `LocalCometLogo`, `Icon` | `activeWorkspace`, settings; workspace/settings actions |
| `shell/ConversationSidebar.svelte` | `AppShell`; `Icon` | conversation ID, sidebar; `setSelectedConversation` |
| `shell/ChatHeader.svelte` | `AppShell`; `Icon`, `StatusBadge` | model/runtime and shell stores; connect/setup/settings/diagnostics actions |
| `shell/SettingsPanel.svelte` | `AppShell`; ModelManager, Observability | control plane, shell, locale, files capability; theme/locale/diagnostics actions |
| `shell/AgentInspector.svelte` | production importer не найден | inspector section/visibility |
| `chat/MessageComposer.svelte` | `AppShell`; FilesPanel, KnowledgeToggle, Icon | draft/conversation/model/files; start/cancel turn, settings |
| `chat/MessageList.svelte` | `AppShell`; EmptyState | chat/model/runtime/acquisition; retry/settings |
| `chat/ApprovalCard.svelte` | production importer не найден | stores нет; обе кнопки disabled |
| `chat/CodeBlock.svelte` | production importer не найден | stores нет |
| `chat/ToolCallCard.svelte` | production importer не найден | stores нет |
| `chat/VerificationCard.svelte` | production importer не найден | stores нет |
| `agent/Diagnostics.svelte` | `AppShell`; Icon, StatusBadge, TelemetryRow, EventStream | control plane, model gateway, inspector visibility |
| `logs/ObservabilityRoom.svelte` | `SettingsPanel`; Icon, StatusBadge, EventStream | control plane/runtime; refresh runtime |
| `files/FilesPanel.svelte` | `MessageComposer`; FilePreviewDialog, Icon | all files stores/actions; initializes capability |
| `files/FilePreviewDialog.svelte` | `FilesPanel` | props only |
| `knowledge/KnowledgeToggle.svelte` | `MessageComposer` | нет; статический non-interactive unavailable status |
| `knowledge/KnowledgePreviewPanel.svelte` | production importer не найден | knowledgePreview store; preview decisions/retry/cancel/source toggles |
| `knowledge/KnowledgeSourceCard.svelte` | `KnowledgePreviewPanel` only | props only |
| `knowledge/KnowledgeStatusBadge.svelte` | `KnowledgePreviewPanel` only | props only |
| `model/ModelManagerSection.svelte` | `SettingsPanel`; StatusBadge | acquisition/runtime/model stores; setup/download/cancel/remove/connect/stop |
| `model/ModelSetupDrawer.svelte` | conditional `AppShell`; Icon, StatusBadge | gateway/runtime/shell; probe/discover/bind/connect/select |
| `model/ModelGatewayPanel.svelte` | production importer не найден | gateway store; external probe/discover/bind/turn actions |
| `model/ManagedRuntimePanel.svelte` | production importer не найден | runtime/inference; refresh/start/stop/bind |
| `onboarding/OnboardingScreen.svelte` | setup workspace; logo/Icon/StatusBadge | acquisition/control plane/runtime; settings/workspace actions |
| `review/ReviewCenterWorkspace.svelte` | review workspace; весь review subtree | review queue/state/selection; load/retry |
| `review/ReviewQueueSidebar.svelte` | ReviewCenterWorkspace; Icon | queue/filters/selection; navigation actions |
| `review/ReviewCommandBar.svelte` | ReviewCenterWorkspace; Icon | queue/state/filters; query/sort/filter/refresh actions |
| `review/ReviewDecisionPanel.svelte` | ReviewCenterWorkspace; dialog/Icon | decision dialog/result and decision setters |
| `review/DecisionConfirmationDialog.svelte` | ReviewDecisionPanel | props; local focus cycling |
| `review/ReviewActivityTimeline.svelte` | ReviewCenterWorkspace | `reviewActivity` |
| `review/ReviewDiagnosticsPanel.svelte` | ReviewCenterWorkspace | `reviewDiagnostics` |
| `review/ReviewFindingsPanel.svelte` | ReviewCenterWorkspace; Icon | review prop |
| `review/ReviewIdentityPanel.svelte` | ReviewCenterWorkspace; Icon | review prop |
| `review/ReviewMetadataPanel.svelte` | ReviewCenterWorkspace | props |
| `review/ReviewTextDiffPanel.svelte` | ReviewCenterWorkspace | review prop |
| `review/ReviewValidationPanel.svelte` | ReviewCenterWorkspace; StatusBadge | review prop |
| `review/RepresentationDeltaPanel.svelte` | ReviewCenterWorkspace; Icon | review prop |
| `common/Icon.svelte` | большинство production surfaces | нет |
| `common/LocalCometLogo.svelte` | navigation, empty, onboarding | нет |
| `common/LocalCometSecurityEmblem.svelte` | PolicyDecision only | нет |
| `common/StatusDot.svelte` | StatusBadge, TelemetryRow | нет |
| `common/StatusBadge.svelte` | many; StatusDot | нет |
| `common/TelemetryRow.svelte` | diagnostics and non-production model panels | props only |
| `common/EventStream.svelte` | Diagnostics, ObservabilityRoom | props only |
| `common/EmptyState.svelte` | MessageList; LocalCometLogo | props only |
| `common/CommandPalette.svelte` | `AppShell` | palette/inspector stores; workspace/settings/diagnostics actions |
| `common/ThemeToggle.svelte` | production importer не найден | theme store/action |
| `common/LanguageSwitcher.svelte` | production importer не найден | locale store/action |
| `common/PolicyDecision.svelte` | production importer не найден | i18n only; supplied risk display |

## Stores

| Store | Экспорты и фактические владельцы записи |
|---|---|
| `stores/shellStore.ts` | theme/workspace/sidebar/inspector/settings/conversation/model/chat/draft/palette/setup state; shell actions and chat reducers; preferences persistence |
| `stores/modelGateway.ts` | gateway, managed runtime, inference, busy/readiness derived stores; bridge lifecycle, runtime/binding, turn start/cancel/retry, strict event reducer; writes chat through shell reducers |
| `stores/controlPlane.ts` | bootstrap/session/thread/mock-turn state and ordered event reducer |
| `stores/artifactAcquisition.ts` | approved artifacts and download state; list/start/follow/cancel/setup/remove; coordinates model store |
| `stores/files.ts` | capability, selected files, inclusion IDs/totals, preview/error; picker/list/preview/forget/report/reset |
| `stores/reviewCenter.ts` | queue, pagination, selection, snapshot, filters, activity, decision dialog/result and controller actions; calls knowledgeReview bridge |
| `stores/knowledgePreview.ts` | preview lifecycle/source state; preview/decide/cancel/retry/fallback and event subscription; component is not production-reachable |
| `stores/uiPreferences.ts` | versioned bounded local preference load/update helper; not a Svelte writable |
| `i18n/index.ts` | `locale`, derived `t`, `setLocale`; updates preferences and document language |

## Tauri bridge and event map

- `bridge/controlPlane.ts`: 7 control-plane commands; event listener `localcomet://control-plane-event` -> `stores/controlPlane.ts`.
- `bridge/modelGateway.ts`: 20 gateway/artifact/runtime/turn commands; same event channel filtered to model events -> `stores/modelGateway.ts`.
- `bridge/files.ts`: 5 fixed file-picker commands -> `stores/files.ts`.
- `bridge/knowledge.ts`: preview/decide and model-start metadata listener -> `stores/knowledgePreview.ts`.
- `bridge/knowledgeReview.ts`: list/get/snapshot/refresh/decision -> `stores/reviewCenter.ts`.
- `bridge/approval.ts`: request/execute/set-workspace wrappers; production caller not found.

No other `@tauri-apps/api/event` channel was found under `src`. Exact command rows are in `21-tauri-commands.md`.

## Production reachability limits

Not in the production render graph: AgentInspector; ApprovalCard/CodeBlock/ToolCallCard/VerificationCard; ThemeToggle/LanguageSwitcher/PolicyDecision; KnowledgePreviewPanel and children; ModelGatewayPanel; ManagedRuntimePanel. Several are directly imported by tests. Their presence/tests do not make them user-reachable.
