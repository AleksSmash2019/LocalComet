# Состояние переноса donor UI

## Копия матрицы экранов

Ниже дословно перенесено содержательное состояние из `audit/donor-screen-port-matrix.md` (mtime `2026-07-26T20:37:50+05:00`). Архив donor `audit/donor-briefs/lad-wp1454.tar.gz` не включён как source content, потому что архивы исключены; его имя и размер есть в `01-tree.txt`.

| Donor area | Disposition | LocalComet decision |
|---|---|---|
| AppShell | ADAPT | Owner-directed override: donor visual shell in Svelte: 224 px labelled navigation, 208 px conversation column, 48 px header, compact typography, flat translucent surfaces, donor palette/borders/radii/focus/responsive states. Existing routing, stores, drawers, accessibility and real Control Plane remain canonical; React/Zustand rejected. |
| Command Center | ADAPT | Centered 768 px chat, compact runtime/model bar, message geometry, empty state and composer around real managed turns, validated streaming, cancellation, selected files and diagnostics. Fake streaming/random telemetry/planner simulation/timers/browser attachments/voice rejected. |
| ModelHub | SUPERSEDED | Existing manager/acquisition uses embedded hash-pinned catalogs, exact bytes, validation/removal/readiness. Static catalog, RAM slider, timer download and mutable Hugging Face flow rejected. |
| Donor model picker | SUPERSEDED | Existing drawer exposes loopback probes, discovered models, approved artifacts, runtime startup/binding. Browser hardware guesses and artificial scan/recommendation rejected. |
| Onboarding | SUPERSEDED | Checklist derives only from Control Plane, approved artifacts, runtime and binding. Unknown remains explicit; no persisted completion/persona/hardware claim. |
| Plan Review | DEFER | No canonical planner request, executable plan, correlated steps/tool result. Approval grants do not dispatch tools. Knowledge Review is separate. |
| SettingsHub | SUPERSEDED | Tabbed settings keeps real theme, locale, diagnostics, capabilities, version, models and observability. Permission profiles, parameters, MCP, reset/export omitted. |
| Logs / Evidence Room | SUPERSEDED | Bounded read-only validated events and sanitized runtime tails, explicitly diagnostic/non-authoritative. Persisted provenance-bearing browser remains DEFER. |
| Multi-chat | DEFER | One global transcript; backend does not reconstruct history by `chat_session_id`. |
| Voice UI | DEFER | No typed voice commands, microphone flow or transcript events; browser SpeechRecognition rejected. |

Implemented ADAPT surfaces in the matrix: Onboarding, tabbed SettingsHub, ObservabilityRoom, compact shell/Command Center/ModelHub/model picker. Explicit rejections: React/Zustand, fake state/random/timers, frontend catalog authority, client logs as evidence, browser SpeechRecognition, and plan execution bypassing Rust approval. Deferred/rejected subpaths: plan execution loop, client-only conversation buckets/export, browser speech, client evidence bundle, RAM/browser recommendation, arbitrary Hugging Face installation.

## Что реально реализовано

- `AppShell.svelte:185-240` routes chat/review/setup, Settings overlay and Command Palette.
- `app.css:38-42` has 48/224/208/768 px shell variables; responsive reductions at `:400,453`.
- `NavigationRail` has real chat/setup/settings buttons; `CommandPalette` is wired to Ctrl/Cmd+K (`AppShell:123-129`).
- Composer submits only through real `startLocalModelTurn` while backend-derived managed readiness is true; cancellation and selected file IDs are wired.
- ModelManager derives artifact/runtime state from stores and backend responses; exact download bytes, confirmation, connect/stop/remove exist.
- Onboarding uses control-plane/catalog/installed/runtime/binding state and displays unknown explicitly.
- Settings has Interface/Models/Logs/About. Observability shows session events and managed stdout/stderr as non-authoritative current-session diagnostics.
- Existing Knowledge Review Center remains independently routed; it is not donor Plan Review.

## Что не реализовано

Plan execution, multi-chat backend history, voice/local STT, persisted evidence browsing/export, permission profiles, model parameters, MCP, reset/export diagnostics, arbitrary Hugging Face installation, RAM recommendation, approval GUI execution, and normal-chat Project Knowledge are absent/deferred/rejected. `KnowledgeToggle.svelte` displays unavailable; approval card controls are disabled.

Legacy demo remnants remain: `stores/controlPlane.ts` invokes `startMockTurn`; Rust registers `control_plane_start_mock_turn`; `mockData.ts` retains reserved conversations, demo assistant/tool/verification/approval/inspector fixtures. Hidden fixture state is not implemented donor functionality.

## Сегодняшнее переопределение главного экрана

По текущему diff и mtime 2026-07-26: shell geometry/palette in `app.css`; root workspace and keyboard command palette in `AppShell`; labelled navigation/conversation columns; compact chat header/messages/composer/empty state; diagnostics restyling; tabbed Settings with model and logs; new CommandPalette, Onboarding and Observability components; i18n additions; shell/model state changes; corresponding layout/component/store tests. Backend runtime changes existed earlier the same day and не являются только visual override.

## Файлы UI-работы с временем изменения

Формат: local time (+05:00), bytes. Timestamps establish filesystem writes, not authorship.

```text
desktop/localcomet-desktop/src/app.css  2026-07-26T20:39:22+05:00  9990
desktop/localcomet-desktop/src/lib/components/agent/Diagnostics.svelte  2026-07-26T20:41:49+05:00  9611
desktop/localcomet-desktop/src/lib/components/chat/ApprovalCard.svelte  2026-07-26T04:27:46+05:00  1305
desktop/localcomet-desktop/src/lib/components/chat/MessageComposer.svelte  2026-07-26T20:41:16+05:00  7552
desktop/localcomet-desktop/src/lib/components/chat/MessageList.svelte  2026-07-26T20:40:56+05:00  5135
desktop/localcomet-desktop/src/lib/components/common/CommandPalette.svelte  2026-07-26T19:44:19+05:00  7622
desktop/localcomet-desktop/src/lib/components/common/EmptyState.svelte  2026-07-26T20:41:39+05:00  2316
desktop/localcomet-desktop/src/lib/components/common/PolicyDecision.svelte  2026-07-26T06:07:13+05:00  1177
desktop/localcomet-desktop/src/lib/components/common/StatusBadge.svelte  2026-07-26T20:41:39+05:00  1465
desktop/localcomet-desktop/src/lib/components/logs/ObservabilityRoom.svelte  2026-07-26T19:31:24+05:00  5940
desktop/localcomet-desktop/src/lib/components/model/ModelManagerSection.svelte  2026-07-26T09:59:15+05:00  13148
desktop/localcomet-desktop/src/lib/components/model/ModelSetupDrawer.svelte  2026-07-26T09:59:15+05:00  19826
desktop/localcomet-desktop/src/lib/components/onboarding/OnboardingScreen.svelte  2026-07-26T19:27:30+05:00  6425
desktop/localcomet-desktop/src/lib/components/shell/AppShell.svelte  2026-07-26T20:37:50+05:00  9541
desktop/localcomet-desktop/src/lib/components/shell/ChatHeader.svelte  2026-07-26T20:46:03+05:00  6389
desktop/localcomet-desktop/src/lib/components/shell/ConversationSidebar.svelte  2026-07-26T20:40:16+05:00  3614
desktop/localcomet-desktop/src/lib/components/shell/NavigationRail.svelte  2026-07-26T20:39:47+05:00  3636
desktop/localcomet-desktop/src/lib/components/shell/SettingsPanel.svelte  2026-07-26T20:41:49+05:00  13144
desktop/localcomet-desktop/src/lib/data/mockData.ts  2026-07-26T19:45:01+05:00  5734
desktop/localcomet-desktop/src/lib/i18n/en.ts  2026-07-26T19:44:19+05:00  35973
desktop/localcomet-desktop/src/lib/i18n/ru.ts  2026-07-26T19:44:19+05:00  52216
desktop/localcomet-desktop/src/lib/risk.ts  2026-07-26T19:44:19+05:00  646
desktop/localcomet-desktop/src/lib/stores/modelGateway.ts  2026-07-26T19:48:17+05:00  47119
desktop/localcomet-desktop/src/lib/stores/shellStore.ts  2026-07-26T19:49:16+05:00  8108
desktop/localcomet-desktop/tests/chat-layout.test.ts  2026-07-26T20:51:07+05:00  5322
desktop/localcomet-desktop/tests/componentSmoke.test.ts  2026-07-26T20:42:36+05:00  4449
desktop/localcomet-desktop/tests/managed-artifacts.test.ts  2026-07-26T19:45:26+05:00  23155
desktop/localcomet-desktop/tests/review-center.test.ts  2026-07-26T19:45:26+05:00  22185
desktop/localcomet-desktop/tests/shellStore.test.ts  2026-07-26T19:50:48+05:00  10510
```
