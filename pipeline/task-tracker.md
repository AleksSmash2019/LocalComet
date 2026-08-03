# LocalComet Task Tracker

## 1. Purpose and authority

This file is the persistent task queue between AI sessions.
The internal OpenCode todo list is NOT a reliable store; this file is.

Sources of truth (descending authority):
1. Bytes on disk, SHA-256, exit codes, test output.
2. git state (branch, HEAD, diff).
3. ADR documents (docs/adr/).
4. pipeline/loop-status.md (session journal).
5. audit/ snapshots.

Markdown journals are NOT absolute authority; claims are verified against code and git diff.
Owner performs acceptance. Agent self-reports are not acceptance.

## 2. Current checkpoint

- Branch: feature/donor-ui-compatible-port
- HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364
- Current work: ADR-015 Phase B COMPLETE (B2-B10 all accepted); P0-C acceptance outstanding
- Phase A (Python gateway): conditionally complete
- Phase B RED-1: complete (T0 GREEN, T1/T2 RED confirmed)
- Phase B GREEN-1: complete (methods registered, deny-by-default branch active)
- Phase B B2-B10: COMPLETE. B10 accepted 2026-07-31 after an independent final
  security review found and closed a FOURTH crash vector of the same class
  (lone surrogate / NUL in the `tool`, `workspace`, `workspace_digest`, `session`
  payload fields, which never pass through `_resolve_in_workspace` but are echoed
  into error messages that the outbound encoder serializes with ensure_ascii=False).
  Fix: `modules/tool_execution_ru.py` `_require_str` -> `_reject_unrenderable`.
  Evidence ledger (39 files, validate.py PASS) lives in the Obsidian vault under
  `99 Handoffs/LocalComet B10 transfer 2026-07-31/B10 evidence ledger`.
- FRESH_VERIFIED_BASELINE Rust (2026-07-31, after the B10 fix):
  - command: cargo test
  - result: 455 passed / 0 failed / 6 ignored
  - exit_code: 0
  - cargo fmt --check: exit 0
  - cargo test b10_: 6 passed / 0 failed
  - python tools/test_v6846_tool_execution.py: 23 tests OK (was 21; +2 regressions)
  - python tools/test_adr015_tool_parsing.py: 64 OK (1 intentional skip)
  - python tools/test_p0c_r1_sidecar_health.py: 31 tests OK, INCLUDING the live
    subprocess probe `test_p0c_r1_live_sidecar_reaches_ready_without_stdout_contamination`
- OBSERVED 2026-07-31: MVP-P0-C-R1 appears IMPLEMENTED in production code
  (`ipc::health_check_request_frame` carries a typed payload, `PendingHealthRegistry`
  and `ipc::parse_health_frame` are on the production path, the `desk-health-` prefix
  heuristic survives only in test fixtures) and the live probe reaches READY.
  This CONTRADICTS the vault snapshot of 2026-07-30 evening, which still records
  `LC_START_102` / "application never starts".
  This observation is EVIDENCE, NOT ACCEPTANCE: `docs/audit/MVP_P0C_ACCEPTANCE.md`
  remains `PENDING EXTERNAL READ-ONLY ACCEPTANCE`. A single in-session run is exactly
  what MVP-P0-C-A1 proved insufficient (84 green tests coexisted with a dead app).
- 2026-08-01: first MVP-P0-C-A2 attempt returned FAIL. Confirmed supervisor
  lifecycle races, stale-reader generation corruption, non-transactional startup
  rollback, stale shipped gateway copies, and missing real-sidecar CI wiring were
  repaired. Bundle parity and local real-sidecar require-mode gate now pass.
- Next exact action: fresh MVP-P0-C-A2 independent read-only acceptance audit
  (8 reviewer sessions, real session IDs, peak concurrency >= 5, writer isolated
  from acceptance). Remediation is evidence, not acceptance. NOT Phase C.
- Prohibited next actions: MVP-P0-D and tool activation before P0-C passes;
  Phase C before P0-C passes; production changes outside authorized scope;
  git commit; file deletion.

## 3. Original OpenCode tracker — historical 3/7 snapshot

Source: exported AI session ses_05e85831affe0Yf97z446Yi5ig
Title: "LocalComet engineer system prompt"
This snapshot is IMMUTABLE. Do not modify, reorder, or split these items.

| # | Status (historical) | Item |
|---|---|---|
| 1 | completed | ADR-013: реализован — принято |
| 2 | completed | ADR-014: реализован — принят условно (финал после коммитов + GUI) |
| 3 | completed | F-TOOL-TRIGGER: DISCOVER выполнен (эмиссия tool calls, tools_available, формат маркеров) |
| 4 | in_progress | F-TOOL-TRIGGER: черновик ADR-015 написан (docs/adr/ADR-015-tool-trigger.md) — ждёт ревью/одобрения, 7 open questions |
| 5 | pending | F-TOOL-TRIGGER: реализация по блокам ПОСЛЕ одобрения ADR-015 (без кода до одобрения) |
| 6 | pending | Follow-up: MockMessage → ChatMessage при следующем касании |
| 7 | pending | Очередь: AgentInspector; ADR-014 follow-ups: персистентность; delete; rename UI; approval-привязка. |

Note: item 7 is ONE historical grouped item. Its sub-tasks are expanded
in section 7 below but remain a single parent in the original seven.

## 4. Reconciled current status

| ID | Original item | Historical | Current status | Evidence | Remaining work | Next gate | Confidence |
|---|---|---|---|---|---|---|---|
| TASK-01 | ADR-013 | completed | DONE | loop-status Blocks 1-6 CLOSED; approval_commands.rs run_tool_call; tool_execution_ru.py; approvalStore.ts; ApprovalCard.svelte; 163 cargo tests | None (do not resurrect) | — | HIGH |
| TASK-02 | ADR-014 | completed/conditional | DONE_CONDITIONALLY | loop-status ADR-014 Blocks 1-5; conversationStore.ts; Sidebar/Header/MessageList/Composer on stores; 308 vitest | Owner acceptance depends on commits + build + GUI | Owner release lane | HIGH |
| TASK-03 | F-TOOL-TRIGGER DISCOVER | completed | DONE | loop-status DISCOVER; pipeline/discovery.md; ADR-015 Problem section | None (do not resurrect) | — | HIGH |
| TASK-04 | ADR-015 draft | in_progress | DONE | ADR-015 APPROVED 2026-07-27; 7 open questions resolved; decisions in ADR body | None | — | HIGH |
| TASK-05 | ADR-015 implementation | pending | IN_PROGRESS | Phase A: 30 tests green; Phase B GREEN-1: 168/0/6; B2 not started | B2-B10, Phase C, Block 3, Block 4 | B2 micro RED | HIGH |
| TASK-06 | MockMessage → ChatMessage | pending | QUEUED | loop-status:253 (owner-added) | Full rename: types, imports, tests, regression scan | After Phase B | HIGH |
| TASK-07 | AgentInspector + ADR-014 follow-ups | pending | QUEUED | loop-status:251-252; ADR-014:180-186; spec.md:28-34 | See section 7 children | After MVP | HIGH |

## 5. ADR-015 execution ladder

### Phase A — Python gateway (CONDITIONALLY COMPLETE)

Implemented (tools/test_adr015_tool_parsing.py, 30 tests):
- TOOL_REGISTRY (5 files.*) + build_tool_schemas (OpenAI function format)
- ToolCallAccumulator: incremental assembly; UTF-8/JSON-escape fragmentation tests
- validate_tool_call: name in registry + schema before emission
- assistant_context parameterized by tools (subset of TOOL_REGISTRY; tools=[] trusted)
- check_model_response_markers: gated rejection (tools_enabled)
- _parse_sse_event: delta.tool_calls parsing
- stream_chat: tools/tool_choice in request body; typed events
- Multi-turn messages: role=assistant(tool_calls) + role=tool(tool_call_id)
- _run_turn: accumulator + model.tool.request emission + terminal model.turn.tool_calls
- Edge cases: mixed content+tool_calls; invalid batch atomic rejection
- MODEL_GATEWAY_EVENTS: +model.tool.request, +model.turn.tool_calls
- tools_executed parameterized (default 0, backward-compatible)

Known limitations:
- install.bat commit-dependent pytest failure (pre-existing, not ADR-015)
- iteration-limit test deferred to Block 3/4
- Real model emission not tested (FakeServer only)

### Phase B — Rust defense-in-depth

Baseline before RED-1: 163 passed / 0 failed / 6 ignored (REPORTED_BASELINE from loop-status)

RED-1 (complete):
- T0 unknown_model_event_method_is_rejected: GREEN guard
- T1 model_tool_request_is_allowed_model_event: RED (unsupported_method)
- T2 model_turn_tool_calls_is_allowed_model_event: RED (unsupported_method)

GREEN-1 (complete):
- model.tool.request added to allowed_event_method + allowed_model_event_method
- model.turn.tool_calls added to allowed_event_method + allowed_model_event_method
- Both routed to specialized deny-by-default branch in validate_and_record_model_event
- Error: protocol_mismatch "tool event semantic validation is not yet implemented"
- Unknown method remains unsupported_method (_ => arm unchanged)
- No permissive acceptance: entry.next_sequence stays 0, event_count stays 0
- Baseline after GREEN-1: 168 passed / 0 failed / 6 ignored (FRESH_VERIFIED_BASELINE, this session)

### Phase B remaining: B2-B10

Each step: micro RED → actual RED cause → minimal GREEN → regression guard → adversarial review.
Do NOT advance until current micro-cycle is GREEN.

| Step | Scope |
|---|---|
| B2 | tools context (events valid only when tools != [] in assistant_context) |
| B3 | registered-tool membership (tool name in TOOL_REGISTRY / risk_level_for_tool) |
| B4 | tool call ID (format, uniqueness within turn) |
| B5 | arguments (valid JSON, schema conformance) |
| B6 | intermediate/terminal consistency (model.turn.tool_calls = sum of model.tool.request) |
| B7 | counters: tools_executed / generated_bytes (gated removal when tools != []) |
| B8 | batch atomicity (invalid call in batch → reject entire batch) |
| B9 | malformed structure (missing fields, wrong types, extra keys) |
| B10 | malicious sidecar defense-in-depth (fuzz-like adversarial payloads) |

### Phase C — Cross-layer parity (after Phase B)

- Python emit ↔ Rust validation ↔ TypeScript parser/types parity test
- tools=[] rejected in ALL three layers
- Terminal batch matches intermediate calls byte-for-byte
- No permissive parsing in any layer
- This is a BLOCKER for Block 2 acceptance (owner condition, 3rd reminder)

## 6. Extended MVP queue

These items are NOT part of the original 3/7 tracker.
Source: loop-status.md:354-369, audit/2026-07-28/05_current_state.md:59-65.

Order:
1. Complete ADR-015 Phase B (B2-B10)
2. Phase C cross-layer parity
3. P0-2 Blind Spots
4. Block 3 frontend orchestration
5. Block 4 E2E/tests/docs
6. Owner release lane

## 8. Ordering correction (2026-07-31)

Section 6 lists the ADR-015 work first, which was accurate while Phase B was open.
With B2-B10 closed, the actual gating order to MVP is:

1. MVP-P0-C-A2 (independent acceptance) — CURRENT GATE
2. MVP-P0-D bundle synchronization milestone (copies are currently synchronized
   as remediation evidence, but this does not authorize tool activation)
3. ADR-015 Phase C cross-layer parity (blocker for Block 2 acceptance)
4. P0-2 Blind Spots
5. Block 3 frontend orchestration
6. Block 4 E2E/tests/docs
7. Owner release lane

P0-D remains prohibited until P0-C passes. Tool activation remains prohibited.
7. P1 (only after MVP critical path)

### P0-2 Blind Spots (owner-authorized, after Block 2 before Block 3)

| ID | Scope | Source |
|---|---|---|
| P0-2A | check_bundle_parity: missing file in shipped runtime → FAIL (not only stale) | loop-status:355 |
| P0-2B | check_evidence_provenance: valid only with exit_code==0 + current tree digest | loop-status:356 |
| P0-2C | trust_chain: deleted/missing file → FAIL (not silent skip at :67-70) | loop-status:357 |
| P0-2D | tool-risk parity: cover tool_execution_ru.py + Rust registry | loop-status:361 |
| P0-2E | AGENTS.md baselines: explicit mandatory gates + fresh numbers | loop-status:358-360 |
| P0-2F | check_mockdata_imports: inert allowlist entries → FAIL | audit 05:defect#8 |
| P0-2G | ChatHeader/ConversationSidebar: remove proven-inert allowlist entries + gate test | audit 05 |
| P0-2H | AgentInspector: linked to TASK-07A; deletion requires owner approval | loop-status:11 |

Each gate fix requires a test proving the gate catches what it previously missed.

### Block 3 — Frontend orchestration

Criteria (ADR-015 section "Изменения по слоям" + owner conditions):
- model.tool.request is INFORMATIONAL only (progress indicator)
- Execute ONCE per turn on terminal model.turn.tool_calls
- read_only: auto-execution + indicator with list of read paths
- guarded/dangerous: ApprovalCard with path + content preview (files.write)
- execute_approved → run_tool_call (INV-APPROVAL-001/002 preserved)
- Tool result returned to model; new turn starts
- Maximum 5 iterations; ≤10 tool calls per turn (frontend enforces)
- Deny → tool-result approval_rejected in history
- Grant issued AFTER confirm click (no expiry during card wait)
- Timeout handling; duplicate terminal rejection; idempotency
- Conversation isolation (approval not leaked across conversations)
- tools=[] fail-closed in frontend (bridge/types)
- No runtime mock; no fake state (INV-UI-001)
- iteration-limit skip removed only after real implementation
- History limit: maximum_messages=32; exceed → invalid_payload

### Block 4 — E2E / TEST / DOCS

Criteria (ADR-015 Phasing Block 4 + owner condition [7]):
- E2E: UI → Rust → Python → model → tool request → validation → execution → result → next turn → final response
- Rust validation exercised
- read_only auto path verified
- approval path verified (guarded/dangerous)
- files.* workspace confinement verified
- Malformed sidecar rejection; invalid batch without partial acceptance
- cancel/deny/timeout paths
- Restart and persistence checks (within in-memory limitation)
- Packaged-runtime smoke
- Coverage table: inverted test → compensating test; net coverage loss = 0
- iteration-limit test becomes active
- Evidence refresh; full gate set

## 7. ADR-014 and UI follow-ups

### TASK-06: MockMessage → ChatMessage

- Status: QUEUED
- Source: loop-status:253 (owner-added follow-up)
- Scope: rename type MockMessage → ChatMessage in all imports, tests, types
- Constraint: perform at next safe touch of the relevant type/file
- Do NOT mix with Phase B
- Separate regression scan mandatory (rg for all references)

### TASK-07: AgentInspector + ADR-014 follow-ups (parent)

Historical status: pending (one grouped item in original 3/7).
Current status: QUEUED. Children below.

#### TASK-07A: AgentInspector

- Component recognized as orphaned (not in production render graph)
- audit/22-frontend-map.md:34 confirms no production importer
- inspectorMock/inspectorSections cannot remain as runtime mock
- Preferred path: delete component + inspectorMock/inspectorSections
- DELETION PROHIBITED without explicit owner approval
- Alternative: real telemetry/Diagnostics integration
- Do NOT start during Phase B

#### TASK-07B: Conversation persistence

- Save conversations and messages across restart
- Define format and migration strategy
- Do NOT mix with current MVP tool-event validator
- Source: ADR-014:190-192 (R1), loop-status:251

#### TASK-07C: deleteConversation

- Store action + UI flow
- Cannot delete last conversation; deleting active switches to neighbor
- Approval/message isolation on delete
- Tests
- Source: ADR-014:184-185, loop-status:252

#### TASK-07D: renameConversation UI

- Store method exists (used by auto-title); inline-rename UI is follow-up
- Localization (i18n keys)
- Tests
- Source: ADR-014:182-183, loop-status:252

#### TASK-07E: Approval binding to conversation

- Approval must belong to specific conversation/turn
- Chat switch must not show or execute another conversation's approval
- deny/approve/idempotency
- Tests
- Source: ADR-014:186, loop-status:252

#### TASK-07F: Control-plane session/thread unification (EXTENDED_FOLLOW_UP)

- NOT part of original seven; discovered later
- Currently chat = model gateway (stateless); control-plane sessions = demo/knowledge
- Unification is architectural work (separate ADR)
- Source: ADR-014:180-181, loop-status:251

## 8. P1 — revalidate before start

Status: REVALIDATE_BEFORE_START for each item.
Do NOT consider historical handover sufficient proof of current relevance.
Each item must be re-checked against current repository before starting.

| Item | Source | Note |
|---|---|---|
| README + SmartScreen documentation | defect #14, ADR-012:14,35 | Two READMEs needed |
| INV-CATALOG-001/002 + INV-MODEL-001 tests | defect #5 (critical, test_ids=[]) | Empty test coverage |
| CI ignore-list inventory | defect #17 | Per-entry: reason + removal plan |
| ADR-011 status → ACCEPTED / 133 files | loop-status:368 | 39 NEEDS_HUMAN + 55 INTERNAL_DEP |
| Legacy NEEDS_HUMAN review | audit 05:debt table | Owner decision per file |

## 9. Owner release lane

These are OWNER actions, not agent permissions.
Agent does NOT perform commits, builds, or installations.

1. Review logical diff groups
2. Prepare commit plan
3. Owner performs commits
4. Full pytest after commits (expect install.bat failure resolved by git rm --cached)
5. Rebuild Tauri bundle
6. Clean build reinstall
7. Refresh evidence after build
8. Re-run bundle parity
9. Packaged smoke test
10. GUI golden path (manual)
11. Real-sidecar with correct env
12. Verify request_model_turn_reserved resolved
13. Verify conversations + auto-title
14. Verify tool execution end-to-end
15. Verify approval flow
16. Verify restart behavior
17. MVP tag only after human acceptance

## 10. Historical work — do not resurrect

| Item | Historical status | Source | Why not active |
|---|---|---|---|
| ADR-008 → ADR-011 (legacy modules) | PROPOSED; 9 DEAD removed | ADR-011; loop-status | Remaining = owner decision (39 NEEDS_HUMAN) |
| ADR-009 → ADR-012 (code signing) | ACCEPTED | ADR-012 | SmartScreen README = P1 |
| Bundle copy-fallback | Removed | ADR-003 | Architectural decision final |
| DIAG cleanup (Block 5) | CLOSED | loop-status:153-160 | Markers removed; functional ok_or_else kept |
| ADR-013 Blocks 1-4 | CLOSED | loop-status:42-127 | Fully implemented + tested |
| ADR-014 Blocks 1-5 | CLOSED | loop-status:225-249 | Fully implemented + tested |
| P0-1 runtime manifest | CLOSED | loop-status:350-352 | tool_execution_ru + workspace_policy added |
| F-TOOL-TRIGGER DISCOVER | CLOSED | pipeline/discovery.md | Fed into ADR-015 |
| ADR-015 Phase A (Python) | CONDITIONALLY COMPLETE | loop-status:277-304 | 30 tests green; known limitations documented |
| Bug #1 (request_model_turn_reserved) | DIAGNOSED | pipeline/discovery.md:7-29 | Fix = bundle rebuild (owner operational) |
| Block 6 chore (whitelist/manifest/hash) | CLOSED | loop-status:190-199 | Test fixes applied |

## 11. Known constraints and unresolved evidence

1. The old internal tracker was NOT a repository source.
   It is recovered from exported session ses_05e85831affe0Yf97z446Yi5ig.
   The "3/7" label cannot be verified from repository alone.

2. Old VERIFICATION_PROTOCOL numbers are historical.
   After GREEN-1 the Rust baseline changed (163 → 168).
   Do not cite old numbers as current without fresh run.

3. Full pytest previously had commit-dependent install.bat failure.
   Do NOT declare full pytest green without fresh run after commits.

4. Iteration-limit test previously skipped until Block 3/4.
   Do NOT remove or mask the skip.

5. AgentInspector deletion requires explicit owner approval.
   No agent may delete it autonomously.

6. Bundled runtime and evidence become authoritative only after
   new build + fresh runs. Current smoke_test 8/8 was against
   stale bundle v6.84.3 (product version 6.84.6).

7. Agent self-reports are NOT human acceptance.
   Only owner sets DONE/ACCEPTED verdicts.

8. Real model (LM Studio) tool_calls emission never tested live.
   All tests use FakeServer. GUI/E2E has no automation.

## 12. Status vocabulary

| Status | Meaning |
|---|---|
| DONE | Complete, verified, no remaining work |
| DONE_CONDITIONALLY | Complete pending owner final acceptance (commits/build/GUI) |
| IN_PROGRESS | Actively being worked on |
| QUEUED | Not started; in line |
| BLOCKED_OWNER | Waiting for owner decision or approval |
| BLOCKED_TECHNICAL | Waiting for technical precondition |
| REVALIDATE_BEFORE_START | Must re-check relevance against current repo before starting |
| HISTORICAL | Closed; do not resurrect |
| UNKNOWN | Cannot determine status |
| SUPERSEDED | Replaced by another item |

ACCEPTED is NEVER set by an agent. Only owner performs acceptance.

## 13. Update protocol

On every tracker change record:
- Date
- Source (file/ADR/test output/git)
- Actual diff or test evidence
- Who changed (agent session ID or owner)
- What became DONE
- Next exact step
- Do NOT erase history
- Do NOT modify the historical 3/7 snapshot (section 3)

## 14. Immediate next action

SUPERSEDED 2026-07-31. The original text below is kept as history.

> ADR-015 Phase B:
> B2 tools context — micro RED→GREEN.
> B2 NOT STARTED at time of tracker creation (2026-07-28).
> Start ONLY after separate owner permission.

Current immediate next action: **MVP-P0-C-A2** — independent read-only acceptance
audit of MVP-P0-C. B2-B10 are complete; B10 was accepted 2026-07-31.

Acceptance constraints carried over from the A1 failure:
- 8 reviewer sessions, real session IDs recorded, peak concurrency >= 5;
- repair and acceptance MUST be different sessions, writer isolated;
- green fixture tests alone are NOT proof — a live process probe is mandatory;
- inherited debts stay honest and are not rewritten: PYTHON_RED_NOT_DEMONSTRATED,
  FRONTEND_RED_NOT_DEMONSTRATED, WRITER_ISOLATION_NOT_PROVEN,
  A1_REVIEWER_FANOUT_NOT_PERFORMED;
- known debts must not grow: B5LP exactly 10 intentional RED, bundle parity exactly 2 stale.

Start ONLY after separate owner permission.

---

Created: 2026-07-28. Session: opencode (qwen3.8-max-preview).
Source: exported session ses_05e85831affe0Yf97z446Yi5ig + repository verification.
Roles executed sequentially (subagents unavailable): session-tracker-analyst,
repository-state-verifier, backlog-reconciler, adversarial-reviewer, task-tracker-writer.
