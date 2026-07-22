# Phase B0 — Project Knowledge Test and Acceptance Plan

Status: `DOCUMENTATION_CONTRACT_ONLY`

This plan separates Phase B0 documentation acceptance from the mandatory gates
for a later, separately authorized implementation. Passing Phase B0 does not
enable Project Knowledge.

## 1. Phase B0 preconditions

- Repository root is `C:\Users\DNS\Documents\LocalComet-build-week-clean`.
- Branch is `continue/after-build-week-2026`.
- Baseline is tag `v0.0.0-build-week-2026` at commit
  `a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`.
- Worktree and index are clean before the documentation change.
- No source code, capabilities, packaging, Vault, AppData, or installed
  application is accessed or modified.

## 2. Phase B0 documentation scope

The only expected additions are:

```text
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_THREAT_MODEL.md
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_TEST_AND_ACCEPTANCE_PLAN.md
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_ROLLBACK.md
```

Phase B0 acceptance requires:

1. The authority document defines selection, consent, revocation, read-only
   boundaries, reparse protection, persistence, lifecycle, limits, refresh,
   redaction, and failure behavior.
2. The threat model identifies assets, trust boundaries, invariants, threats,
   mitigations, and residual risk.
3. This plan defines positive, negative, regression, packaged, and rollback
   acceptance for later implementation.
4. The rollback plan preserves the source and separates documentation rollback
   from future feature rollback.
5. The four documents do not claim that Project Knowledge is production-ready.

## 3. Phase B0 repository checks

Run from the repository root:

```powershell
$phaseB0Docs = @(
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md',
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_THREAT_MODEL.md',
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_TEST_AND_ACCEPTANCE_PLAN.md',
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_ROLLBACK.md'
)
$documentCheckFailed = $false
foreach ($document in $phaseB0Docs) {
  $resolvedDocument = (Resolve-Path -LiteralPath $document).Path
  $documentLines = [System.IO.File]::ReadAllLines($resolvedDocument)
  for ($lineIndex = 0; $lineIndex -lt $documentLines.Length; $lineIndex++) {
    if ($documentLines[$lineIndex] -match '[ \t]+$') {
      Write-Error "${document}:$($lineIndex + 1): trailing whitespace"
      $documentCheckFailed = $true
    }
  }
  $documentBytes = [System.IO.File]::ReadAllBytes($resolvedDocument)
  if ($documentBytes.Length -eq 0 -or $documentBytes[-1] -ne 10) {
    Write-Error "${document}: missing final newline"
    $documentCheckFailed = $true
  }
}
if ($documentCheckFailed) { throw 'Phase B0 document check failed' }
git diff --check
git --no-pager diff --name-status
git --no-pager status --short --untracked-files=all
```

Because `git diff --check` does not inspect untracked files, the explicit
four-file check above is mandatory while the documents are untracked. After the
files are staged by an authorized later action, also run:

```powershell
git diff --cached --check
```

Expected result:

- The explicit four-file check reports no trailing whitespace and confirms a
  final LF byte in every document.
- `git diff --check` exits `0` with no output.
- After staging, `git diff --cached --check` exits `0` with no output.
- Exactly the four Phase B0 Markdown files are untracked or changed.
- No staged change, deletion, source file, generated artifact, or unrelated path
  is present.

No Python compilation, npm, Cargo, installer, stability, UI automation, or
installed-application test is required for the documentation-only change.

## 4. Future implementation test environment

All filesystem tests MUST use fresh disposable synthetic fixtures. The positive
source fixture MUST be a valid LocalComet Vault v2 root. Tests MUST set
test-specific source, protected-project, configuration, and application-data
roots. They
MUST NOT read or write:

- a real Obsidian Vault;
- the normal LocalComet AppData root;
- the installed LocalComet application;
- `Projects/BrowserProfile`;
- `C:\Users\DNS\Documents\LocalAgent`; or
- any source directory not created by the test itself.

Tests must disable bytecode and other repository-local caches where applicable.
Generated frontend, Rust, and installer validation belongs in an ignored or
external clean-room workspace.

## 5. Source-selection and consent tests

Automated and component tests must prove:

- initial state is `NOT_CONFIGURED`;
- only an explicit native-picker action starts selection;
- cancelling the picker causes no read and no state change;
- before confirmation, Rust inspects only root type, root reparse status, fixed
  local-volume identity, and sanitized display name;
- descendant entries, descendant metadata, and source contents are not read
  before confirmation;
- the confirmation shows the read-only boundary, limits, persistence choice,
  revocation behavior, and no-model-send statement;
- only `Use this folder read-only` creates source consent;
- `THIS_SESSION_ONLY` is the default;
- `REMEMBER_SOURCE` requires an additional explicit choice;
- choosing a second source atomically revokes the first;
- frontend payloads cannot supply or recover an absolute path; and
- malformed, unknown, duplicate, or replayed consent requests fail closed;
- a Review Center decision cannot create source consent, remembered consent,
  filesystem authority, or per-turn inclusion consent; and
- no repository, application checkout, environment path, or project root is
  inferred or inspected when no source has been explicitly selected.

## 6. Read-only and containment tests

Positive fixtures must cover a disposable valid LocalComet Vault v2 root and
deterministic `vault_revision` generation. A generic Markdown-only directory
without the required Vault v2 schema is an unsupported negative fixture, not a
positive source.

Negative fixtures must cover:

- empty, relative, drive-relative, UNC, URL, device, and file paths;
- volume root, user-profile root, AppData root, install root, and temporary root;
- root symlink, root junction, ancestor reparse point, nested directory link,
  file link, mount point, cloud reparse placeholder, and unknown reparse tag;
- `..`, mixed-separator traversal, case-fold collision, Unicode normalization
  collision, reserved Windows names, alternate data streams, and control chars;
- a file replaced, renamed, deleted, resized, or converted to a link during read;
- a path resolving outside the root after validation; and
- unsupported regular files and non-regular filesystem entries.

Every reparse tag and every cloud placeholder MUST be rejected; tests must not
define a safe-tag exception. A native integration test must also force the
no-follow-open or post-open identity primitive to be unavailable and prove that
the scan fails closed rather than falling back to a path-based read.

Vault v2 notes containing external `source_paths` must be tested with a protected
synthetic project root and with the application checkout as a sentinel. Without
a separate project-root authority and explicit consent, the values remain inert:
no resolve, stat, directory enumeration, or file open may target either root.
The production test must prove there is no implicit repository-root fallback.

For every case, assert no content escapes the root, no partial index activates,
no source entry changes, and the returned error is sanitized.

Read-only tests must snapshot fixture names, bytes, SHA-256 values, attributes,
and write timestamps before and after selection, scan, preview, refresh,
cancellation, revocation, restart, and shutdown. Any LocalComet-created file or
content/attribute/write-time change is a failure. Operating-system access-time
behavior is recorded separately and is not represented as a LocalComet write.

## 7. Limit and resource tests

Test the exact boundary and first rejected value for:

- traversal depth `32` / `33`;
- filesystem entries `10,000` / `10,001`;
- Markdown notes `2,000` / `2,001`;
- note bytes `1,048,576` / `1,048,577`;
- aggregate Markdown plus authorized auxiliary content bytes `67,108,864` /
  `67,108,865`;
- auxiliary bytes `1,048,576` / `1,048,577`;
- query characters `4,096` / `4,097`;
- desktop results `8` / `9`;
- selected sections `3` / `4`;
- excerpt characters `1,200` / `1,201`;
- preview context characters `12,000` / `12,001`; and
- scan wall time within / beyond `30` seconds.

Also test cancellation during enumeration, hashing, validation, retrieval, and
refresh; repeated refresh requests; one-active-operation enforcement; bounded
memory/event output; and absence of orphan workers after cancellation.

Aggregate-byte fixtures MUST combine Markdown, regular `*.base`, and the single
authorized `00 Канон/LocalComet — Архитектурная карта.canvas` content. They must
prove that every content byte is charged before the open and that
`.obsidian/*.json` content is never opened. No other auxiliary content is
authorized.

Cancellation tests MUST close admission and increment the source generation
before signalling cancellation, join active work within exactly 5 seconds, and
reject every result carrying the prior generation. A deterministic blocking
fixture must prove that a result arriving after cancellation cannot activate an
index or preview. Missing the 5-second join deadline is an acceptance failure.

## 8. Refresh, revision, and preview tests

Tests must prove:

- the first complete scan atomically activates one index;
- identical bytes produce the same deterministic `vault_revision`;
- a successful changed scan atomically replaces the old index;
- a failed scan activates no candidate and marks the old state `DEGRADED`;
- `DEGRADED` state cannot prepare a new preview;
- preview content is bounded and includes relative provenance and truncation;
- preview identity binds source ID, source generation, `vault_revision`, turn ID,
  selected content hashes, and preview digest;
- any source change between preview and decision invalidates the decision;
- an approval cannot be replayed for another turn, preview, source, or
  `vault_revision`;
- `REJECT_AND_SEND_WITHOUT_KNOWLEDGE` contains no source text;
- `CANCEL` causes no model call; and
- retry after revocation contains no prior context.

## 9. Persistence and revocation tests

For `THIS_SESSION_ONLY`, verify no source record is written and restart returns to
`NOT_CONFIGURED`.

For `REMEMBER_SOURCE`, verify only the approved versioned semantic metadata is
stored by Python, Rust stores no duplicate semantic consent, no note or preview
content is stored, and no absolute path appears in frontend storage. Invalid,
truncated, unknown-version, or tampered records must fail closed.

Revocation tests must prove admission closes and generation increments before
cancellation, active work is joined within exactly 5 seconds, prior-generation
results are discarded, pending previews become invalid, Python-owned consent is
removed, volatile content is cleared, the operation is idempotent, and the
source remains byte-identical.

Crash and abnormal-exit tests must prove unfinished scans and approvals are not
recovered as valid.

## 10. Redaction and failure tests

Inject synthetic absolute paths, usernames, API keys, bearer tokens, private
keys, credentials, environment values, malformed Unicode, long exception text,
and source excerpts into every failure layer.

Assert that logs, Rust errors, Python errors, events, diagnostics, and frontend
state contain only stable codes and approved bounded fields. Raw exception repr,
source body, prompt, secret value, and absolute path must be absent.

Secret-like content must block the affected scan or preview without repeating
the value. Failure must leave ordinary chat usable and must never silently send
the turn with knowledge.

## 11. Capability-negative tests

Repository, generated capability, and packaged scans must prove that the
implementation adds no:

- generic filesystem, shell, process, environment, URL, HTTP, or raw IPC command;
- frontend-supplied path, executable, argument, hash, or approval identity;
- source write, repair, sync, migration, export, deletion, or watcher;
- network share, remote knowledge source, cloud embedding, telemetry, or update;
- automatic knowledge inclusion or remembered turn approval;
- generic Markdown source support, implicit repository/project-root discovery,
  or resolution of inert external `source_paths`;
- use of a Review Center decision as consent or filesystem authority;
- tool, browser, computer-use, email, connector, or publication authority; or
- change to the existing model/artifact trust contract unrelated to Project
  Knowledge.

## 12. Regression gates for a future code change

After focused tests pass, run the repository-supported affected Python suites,
changed-file compilation, complete frontend tests/check/build, Rust formatting,
locked/offline Cargo check, warnings-denied Clippy, Rust tests, sidecar contract
checks, package-source verification, and the normal clean-room offline NSIS
build.

The current KnowledgeAdapter and Vault v2 validator are not production-
conforming until a separately authorized change replaces path-based reads with
mandatory no-follow opens and post-open type, identity, and containment
verification. Regression gates cannot waive this requirement.

The existing local-model lifecycle must still pass: approved acquisition,
connect, real text response, Stop, Retry, disconnect, clean shutdown, and no
managed orphan. Ordinary chat with Project Knowledge unavailable, rejected, or
revoked must remain functional.

`stability test` is required after an important Python implementation change,
with any generated reports kept outside the committed source set.

## 13. Packaged acceptance for a future implementation

Use a disposable valid LocalComet Vault v2 fixture source and isolated
application-data root. Verify:

1. fresh install starts with Project Knowledge unavailable;
2. native selection and confirmation work without exposing an absolute path;
3. a valid source becomes ready and produces a local preview;
4. reject sends an ordinary turn with zero knowledge bytes;
5. include sends the exact preview and produces one local response;
6. modifying the fixture after preview forces a refresh;
7. revocation stops future use and preserves the fixture byte-for-byte;
8. remembered versus session-only behavior survives restart exactly as defined;
9. malformed/reparse/oversized fixtures fail safely;
10. normal closure leaves no app, sidecar, model-runtime, or scan worker orphan;
11. uninstall and reinstall do not modify the fixture; and
12. no protected normal-profile Vault or AppData root is opened by the LocalComet
    process tree.

Record process identity, isolated roots, exact fixture manifest, commands, exit
codes, UTC times, and sanitized results. Do not record source content, prompts,
personal paths, or credentials.

Item 12 requires a Windows filesystem-access audit. Start ProcMon capture before
launch and filter to the complete LocalComet process tree, including the desktop
process, Python sidecar, model runtime, and scan workers. Filter filesystem
events whose path begins with either the predeclared normal-profile LocalComet
AppData root or the predeclared real-Vault root. At minimum include open,
`CreateFile`, directory-query, read, write, rename, delete, and metadata-change
operations. An ETW Kernel-File capture with equivalent PID-tree and path-prefix
correlation is an acceptable substitute.

The protected path strings are supplied to the local audit filter without
probing their existence or contents. Audit output is written only to the
isolated clean-room evidence root. Acceptance requires zero matching LocalComet
process-tree events; audit-tool self-events are excluded by process identity. A
sanitized published summary records hashes or labels for protected roots, event
filters, capture interval, process tree, and zero-event result, never the
personal path strings. If ProcMon or equivalent ETW evidence is unavailable,
item 12 is unproven and packaged acceptance is blocked.

## 14. Acceptance decision

Phase B0 documentation passes when Section 3 passes and the four documents cover
all requested authority topics without changing product behavior.

A future implementation passes only when Sections 4–13 pass with zero
unexplained failure, zero source mutation, zero authority expansion, and a clean
worktree. Any missing owner decision, unsafe path behavior, unredacted content,
stale-preview acceptance, source mutation, or incomplete packaged evidence is a
release blocker.
