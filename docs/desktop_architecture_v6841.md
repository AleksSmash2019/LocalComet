# LocalComet Desktop Architecture v6.84.1

## 1. Purpose and Scope

v6.84.1 defines the contract-first foundation for a professional Windows desktop LocalComet application. It describes the intended desktop architecture and implements only the Python-side IPC protocol helpers in this release.

This release does not scaffold Tauri, Rust, SvelteKit, Node, npm, pnpm, Cargo, a sidecar process, a GUI, a localhost server, or the v6.85 autonomous loop.

## 2. Final Desktop Technology Stack

- Desktop shell: Tauri 2.
- Web runtime: one primary WebView using system WebView2 on Windows.
- Frontend: SvelteKit with TypeScript strict mode.
- Production frontend build: static adapter, no server-side rendering inside the packaged desktop application.
- Trusted native bridge: Rust.
- Core intelligence: existing Python LocalComet modules packaged as a sidecar.
- Production transport: framed JSON over dedicated stdin/stdout pipes.

The application must not embed Chromium, open an external browser window, or expose a production localhost HTTP/WebSocket API.

Open WebUI is only a visual-structure reference; LocalComet is not a source-code fork and must not copy Open WebUI source, branding, component names, styling files, logos, or proprietary assets.

## 3. Trust Boundaries

The frontend is not trusted for policy decisions, filesystem authorization, process execution, approval generation, secret storage, or autonomy-level selection.

Rust is trusted for process lifecycle, native window lifecycle, Tauri capabilities, outer IPC envelope validation, native dialogs, and future Windows child-process containment.

Python is trusted for semantic request validation, planning, policy decisions, action execution, run state, diagnostics, preflight, audit bundles, model orchestration, and redaction.

No layer may trust data merely because it came from another local process.

## 4. Process Topology

The target production topology is:

```text
Tauri window (SvelteKit static UI)
  -> Rust command bridge
    -> one child Python LocalComet sidecar
      -> existing LocalComet modules
```

The Svelte UI communicates only with narrow Rust commands. Rust owns the Python process handle and framed pipe transport. Python owns LocalComet semantics.

## 5. Frontend Responsibilities

SvelteKit owns transient interface state:

- open panels;
- draft composer text;
- selected conversation;
- visible filters;
- local UI affordances;
- optimistic rendering of pending events.

Svelte must not read arbitrary files, execute processes, read environment variables, manufacture approvals, change policy levels, or store sensitive content in browser localStorage.

## 6. Rust Bridge Responsibilities

Rust owns:

- Tauri window setup;
- Tauri command registration;
- native dialog mediation;
- Python sidecar startup and shutdown;
- framed stdin/stdout transport;
- outer-envelope validation;
- bounded outbound event queue;
- future Windows Job Object containment;
- production capability enforcement.

Rust does not make autonomy decisions, reinterpret prompts, or execute arbitrary shell text.

## 7. Python Sidecar Responsibilities

Python remains authoritative for:

- chat/model orchestration;
- planning;
- policy and approvals;
- safe action execution;
- immutable run state;
- diagnostics;
- preflight;
- audit bundle creation and verification;
- redaction and sanitized errors.

stdout must contain only framed IPC messages. stderr is reserved for bounded sanitized diagnostics.

## 8. IPC Framing

Protocol name: `localcomet.ipc`.

Protocol version: `1.0`.

Each frame is:

1. four-byte unsigned big-endian length;
2. exactly that many UTF-8 JSON bytes.

There are no delimiter-based frames. Maximum frame size is 4,194,304 bytes. Zero-length frames, malformed UTF-8, malformed JSON, duplicate keys, NaN, Infinity, oversized payloads, unknown envelope types, and unsupported protocol versions are rejected.

## 9. IPC Message Lifecycle

Rust sends `hello`. Python answers with a `hello` response payload selecting version `1.0`. Requests then flow from Rust to Python, and Python returns exactly one terminal response or error for each request.

Events may appear between request acceptance and terminal completion. Events after terminal completion are rejected or ignored deterministically by stream state.

## 10. Streaming and Backpressure

Streaming uses ordered `event` envelopes with `reply_to` set to the originating request ID. `chat.delta` batches text instead of sending one token per frame. Maximum delta text is 65,536 characters.

Future defaults:

- maximum queued events: 1,000;
- maximum queued text: 8 MB;
- delta coalescing window: 10-30 ms.

Rust pauses sidecar reads or cancels the request if the UI cannot keep up. No layer may use an unbounded event buffer.

## 11. Cancellation

Cancellation is a `cancel` envelope containing `target_request_id` and a bounded reason:

- `user_requested`;
- `window_closing`;
- `timeout`;
- `shutdown`.

Cancellation is idempotent, cannot approve actions, cannot expose process handles, and produces a terminal response or terminal error for the cancelled request.

## 12. Approval Flow

`approval.required` events contain only sanitized metadata: action ID, fingerprint, risk, summary, sanitized target, reversibility, and optional expiration.

`approval.submit` includes action ID, action fingerprint, decision `approve|deny`, and scope `SINGLE_ACTION`.

Frontend text such as "yes" is not approval. The UI cannot change action fingerprints or policy level. Approval cannot override permanent policy blocks.

## 13. File Attachment Flow

Normal IPC messages do not stream arbitrary file bytes.

Future flow:

1. Svelte requests a native file picker through a narrow Tauri command.
2. Rust validates the selection.
3. Rust creates an opaque attachment handle.
4. Svelte sees handle, sanitized filename, size, and media type.
5. Python accesses the file only through an explicitly authorized bridge flow.

Absolute paths are never exposed to Svelte.

## 14. Model Integration Flow

Python owns model configuration and orchestration. Rust forwards bounded requests and streams sanitized events. Svelte renders model state but does not hold authoritative credentials or endpoint configuration.

## 15. Autonomous-Agent Event Flow

Future autonomous events include plan updates, proposed actions, approval requests, policy decisions, budget changes, test results, rollback state, and kill-switch changes. v6.84.1 defines the IPC shape only and does not activate the v6.85 loop.

## 16. Process Startup

Rust starts the Python sidecar after window initialization and capability setup. The first sidecar message must be a framed hello response. Any informal stdout text is a protocol error.

## 17. Process Shutdown

Rust sends `goodbye` or cancellation during shutdown, closes stdin, drains bounded output, and terminates the child if it does not exit. Python should finish active cleanup without writing persistent state unless a later release explicitly owns that state.

## 18. Crash Handling

Rust detects sidecar exit, emits sanitized UI state, and prevents stale approvals. Python error messages must use bounded error codes and sanitized details. Tracebacks are never sent to the frontend.

## 19. Windows Process Containment

Windows Job Object containment is the target mechanism. It is not implemented in v6.84.1. Child-process tree containment belongs to a later release and must be verified before claiming support.

## 20. CSP and Tauri Capabilities

Future Tauri requirements:

- CSP `default-src 'self'`;
- no remote JavaScript;
- no eval;
- no wildcard `connect-src` in production;
- narrow capabilities per window;
- no shell plugin exposed to the frontend;
- no broad filesystem plugin;
- no unrestricted process plugin;
- signature validation for updater endpoints;
- no production debug console unless explicitly enabled;
- disable navigation outside bundled app;
- external URLs opened only through an allowlisted Rust command;
- sanitized drag-and-drop metadata.

## 21. Secret Handling

Secrets remain in Python or OS-native secure storage when later introduced. They are not stored in browser localStorage. Logs, IPC errors, and events must redact tokens, passwords, Authorization headers, private keys, full user paths, raw write content, and attachment paths.

## 22. Logging and Redaction

Rust and Python log only sanitized protocol metadata, bounded IDs, methods, counters, and safe status fields. Payload text is truncated and redacted. stdout from Python is never used for informal logs.

## 23. Data Ownership

Svelte owns transient UI state only.

Rust owns process handles, IPC channel state, window state, and update state. Rust does not own the conversation database.

Python owns conversations, model configuration, planner results, autonomy runs, approvals, tool results, diagnostics, and audit metadata.

## 24. State Persistence Ownership

Persistent LocalComet state remains Python-owned. Svelte may cache cosmetic preferences only if they do not contain sensitive data. Rust may persist window geometry and updater state.

## 25. Error Model

Errors use bounded codes such as `invalid_frame`, `invalid_json`, `invalid_envelope`, `unsupported_version`, `unsupported_method`, `request_cancelled`, `policy_blocked`, `approval_required`, `kill_switch_active`, and `internal_error`.

Error payloads contain code, sanitized message, retryable flag, and bounded details. They never include tracebacks, raw exception reprs, environment variables, full paths, source contents, or secret values.

## 26. Version Negotiation

The initial release supports only protocol `1.0`. Rust sends supported versions in hello. Python selects `1.0` or returns `unsupported_version`.

## 27. Compatibility Strategy

Future minor protocol additions must preserve existing fields and bounded vocabularies. New methods should be additive. Breaking changes require a new protocol version and explicit negotiation.

## 28. Threat Model

Threats include prompt injection, malicious attachments, compromised frontend state, overlarge frames, malformed JSON, duplicate keys, path disclosure, secret leakage, unauthorized approval, sidecar crash, event queue exhaustion, and subprocess containment gaps.

Mitigations include strict framing, schema and Python validation, redaction, opaque handles, exact approval fingerprints, policy recomputation, capability-limited Rust commands, and no exposed production HTTP API.

## 29. Development Mode

Later development workflows may use a Vite development server. That must not alter production trust boundaries. Production loads bundled static assets only.

## 30. Production Mode

Production uses a signed Tauri application, bundled static Svelte assets, one Python sidecar, length-prefixed JSON pipes, no exposed production localhost API, no localhost server, and no external browser window.

## 31. Packaging Plan

Later releases package:

- Tauri binary;
- static Svelte assets;
- Python runtime or validated environment strategy;
- LocalComet Python modules;
- schema files;
- signed updater metadata.

## 32. Installer Plan

The installer should create per-user application files, avoid requiring administrator rights by default, register uninstaller metadata, and not install services or scheduled tasks unless a later release explicitly designs them.

## 33. Signed Updater Plan

Updater metadata and payloads must be signature-verified. Unsigned updater endpoints are not allowed. Rollback and staged rollout policy belong to a later release.

## 34. UI Information Architecture

Navigation rail width: 52-60 px. Items: new chat, search, conversations, projects, autonomous runs, models, tools, diagnostics, settings.

Expandable sidebar width: 240-320 px. Contains conversation history, projects, pinned sessions, filters, and local search.

Center workspace contains header, model selector, mode selector (`Chat`, `Plan`, `Agent`), virtualized message list, Markdown, code blocks, tool-call blocks, attachments, approval cards, and floating composer.

Agent inspector width: 320-420 px. Contains agent status, current plan, current action, risk level, policy decision, approval request, budgets, changed files, diff, test results, preflight, rollback state, and kill-switch status. It is collapsible.

Below about 1,200 px, the inspector hides behind a toggle. Below about 900 px, the history sidebar collapses. The desktop window minimum size target is 900 x 640.

## 35. Component Hierarchy

Future original LocalComet components:

- `AppShell`;
- `NavigationRail`;
- `ConversationSidebar`;
- `WorkspaceHeader`;
- `ModelSelector`;
- `ModeSelector`;
- `MessageTimeline`;
- `MarkdownMessage`;
- `CodeBlock`;
- `ToolCallBlock`;
- `ApprovalCard`;
- `FloatingComposer`;
- `AgentInspector`;
- `BudgetPanel`;
- `DiffPanel`;
- `DiagnosticsPanel`.

These names are LocalComet-owned and are not copied from any external project.

## 36. Accessibility Requirements

All controls require keyboard operation, visible focus rings, semantic labels, high-contrast status colors, screen-reader names for icon buttons, reduced-motion support, and predictable tab order. Approval actions must be confirmable without relying on color alone.

## 37. Performance Targets

Targets:

- first window paint under 1.5 seconds after native startup on a warm machine;
- message list virtualization for long conversations;
- IPC frame validation under 5 ms for ordinary frames;
- no unbounded queues;
- bounded Markdown/code rendering work;
- responsive composer input under streaming load.

## 38. Migration Stages

1. v6.84.1: architecture, schema, Python IPC helpers.
2. v6.84.2: visual Tauri/Svelte shell scaffold.
3. Later: Rust bridge process lifecycle and framing.
4. Later: Python sidecar packaging.
5. Later: model/chat IPC integration.
6. Later: agent inspector and approval flow.
7. Later: signed installer/updater.

The existing Tkinter control panel remains a temporary fallback during this migration and is not modified by the desktop architecture releases.

## 39. Acceptance Criteria

This architecture is acceptable when it preserves LocalComet's current Python authority, avoids production localhost APIs, keeps the frontend untrusted for security decisions, uses bounded framed JSON IPC, documents containment honestly, and reserves future document workflows without implementing them.

## 40. Deferred Capabilities

Deferred capabilities include visual UI implementation, Tauri project scaffolding, SvelteKit build setup, Rust IPC bridge implementation, Python sidecar process management, Windows Job Object containment, signed updater, attachment picker, v6.85 autonomous loop, and document workflow execution.

## 41. Structured Document Workflows

The desktop architecture reserves a future bounded document-workflow subsystem. It is not implemented in v6.84.1.

Future pipeline:

```text
source ingestion
-> content extraction
-> schema selection
-> typed field extraction
-> missing-field detection
-> human confirmation
-> deterministic template rendering
-> artifact verification
-> desktop preview/export
```

Rules:

- LLMs must not render final business documents directly.
- LLMs may classify intent, extract candidate fields, and identify missing data.
- Deterministic code validates structured fields.
- A bounded renderer creates the artifact.
- Typst may be evaluated later as one renderer option.
- Rendering subprocesses must use the v6.84 safe executor.
- No shell execution is permitted.
- Fixed executable and template allowlists are required.
- Timeout and output limits are required.
- Each run uses a unique artifact directory.
- Writes are atomic and verified with SHA-256.
- Sensitive documents remain local by default.
- External model upload requires explicit one-time approval.
- Attachment filenames are never trusted as paths.
- Email and other connectors remain disabled by default.
- Frontend receives opaque attachment and artifact handles, not absolute paths.
- Generated artifacts appear as dedicated UI cards and in the Agent Inspector.
- Missing required fields appear as structured confirmation forms.
- No document, email, or attachment implementation is added in v6.84.1.

Reserved future IPC events:

- `document.ingestion.started`;
- `document.ingestion.completed`;
- `document.fields.extracted`;
- `document.fields.required`;
- `document.confirmation.required`;
- `document.rendering.started`;
- `document.artifact.created`;
- `document.verification.completed`;
- `document.failed`.

Reserved future UI components:

- `DocumentWorkflowCard`;
- `MissingFieldsForm`;
- `ArtifactCard`;
- `ArtifactPreview`;
- `ArtifactVerificationBadge`.

## 42. Visual Tokens

LocalComet visual tokens must be original.

light theme:

- background: `#f7f8fb`;
- surface: `#ffffff`;
- elevated surface: `#f1f4f8`;
- text: `#15202b`;
- muted text: `#637083`;
- border: `#d7dde6`.

dark theme:

- background: `#101316`;
- surface: `#171b20`;
- elevated surface: `#20262d`;
- text: `#eef2f7`;
- muted text: `#a2adbb`;
- border: `#343c46`.

Spacing: 4 px base scale with 8, 12, 16, 24, and 32 px layout steps.

Radii: 4 px for controls, 6 px for panels, 8 px maximum for repeated cards.

Typography: system UI stack, 13-14 px dense controls, 15-16 px reading text, tabular numerals for counters.

Semantic statuses:

- success: green;
- warning: amber;
- danger: red;
- paused: blue;
- neutral: gray.

Risk colors:

- LOW: muted green;
- MEDIUM: amber;
- HIGH: orange-red;
- CRITICAL: red with high-contrast treatment.

Approval colors separate approve, deny, pending, and expired states. Focus rings use a two-layer high-contrast outline. Code surfaces use a monospace font, line wrapping, copy affordance, and no negative letter spacing.
