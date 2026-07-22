# Phase B0 — Project Knowledge Source Authority

Status: `DOCUMENTATION_CONTRACT_ONLY`

Baseline tag: `v0.0.0-build-week-2026`

Baseline commit: `a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`

Phase B0 defines the authority boundary for a future production Project
Knowledge integration. It does not enable Project Knowledge, grant filesystem
authority to the current frontend, read a knowledge source, or authorize source
code, capability, packaging, AppData, Vault, or installed-application changes.

The words MUST, MUST NOT, SHOULD, and MAY are normative.

## 1. Objective

Permit a user to make one valid LocalComet Vault v2 root available as an
explicitly selected, read-only Project Knowledge source while preserving these
invariants:

- LocalComet never chooses a source implicitly.
- Selecting a source does not send its content to a model.
- Source content reaches a model only after an exact local preview and a
  separate per-turn user decision.
- Ordinary local chat remains available without Project Knowledge.
- The selected source is never modified by LocalComet.

The first supported source contract is the LocalComet Vault v2 contract enforced
by the validator at the Build Week baseline. A directory containing arbitrary
Markdown without the required Vault v2 schema is not a supported source.
Generic Markdown directories are deferred to a separate authority decision.

## 2. Authority granted by this contract

A later, separately authorized implementation MAY add a bounded production
source-selection flow that conforms to this document. That authority is limited
to one local Vault v2 source, read-only validation, in-memory indexing, bounded
retrieval, local preview, and exact per-turn inclusion.

This contract does not authorize:

- arbitrary frontend filesystem access or a generic path/handle command;
- selecting more than one source;
- automatic repository discovery or use of the application checkout;
- defaulting to, deriving, probing, or inspecting a repository or project root
  for Vault v2 validation;
- reading a project root referenced by note metadata;
- treating a generic Markdown directory as a supported source;
- writes, edits, synchronization, import, export, indexing databases, or lock files
  inside the selected source;
- network, cloud, connector, browser, email, shell, process, tool, telemetry, or
  publication authority;
- using Project Knowledge as long-term conversational memory;
- background ingestion before consent or after revocation;
- model training, fine-tuning, embeddings downloads, or remote vector services.

## 3. Source-selection flow

The initial production state MUST be `NOT_CONFIGURED` and Project Knowledge MUST
remain unavailable without a valid consent record.

The user selects a source through this future flow:

1. The user opens Settings → Project Knowledge and activates `Choose folder`.
2. Rust opens the native Windows directory picker. The frontend MUST NOT accept,
   construct, paste, or retain an absolute path.
3. Picker cancellation changes no state and performs no source scan.
4. Rust may inspect only the candidate's root type, root reparse status, fixed
   local-volume identity, and sanitized display name needed for the confirmation
   screen. This four-field allowance is exhaustive. It MUST NOT enumerate a
   descendant, inspect descendant metadata, open a source file, or read source
   content before source consent.
5. LocalComet shows a confirmation containing a sanitized folder display name,
   the read-only promise, supported content, scan limits, persistence choice,
   revocation behavior, and the statement that selection does not send content
   to a model.
6. The user explicitly activates `Use this folder read-only`. Merely choosing a
   folder in the native picker is not source consent.
7. Rust mediates the selected path and creates an opaque source handle. Python
   validates the boundary and Vault v2 contract and begins one bounded scan. The
   frontend receives only an opaque source ID, sanitized display name, state,
   counts, `vault_revision`, and safe findings.

The first implementation MUST support exactly one active source. Choosing a new
source requires a new confirmation and atomically revokes the old source before
the new scan begins. Failure of the new source MUST leave Project Knowledge
disabled; it MUST NOT silently reactivate the old source.

## 4. Consent model

Project Knowledge has two independent consent gates.

### 4.1 Source consent

Source consent authorizes LocalComet to enumerate, validate, and read bounded
supported files beneath the exact selected root. It does not authorize model
inclusion, writes, external project reads, or network use.

Vault v2 `source_paths` values are inert provenance in the first implementation.
LocalComet MUST NOT resolve, stat, open, or otherwise inspect them against a
repository or project root. Project-root consent is a separate authority that is
not granted by Phase B0; unless a later contract and a separate explicit user
consent grant it, external `source_paths` remain inert.

The confirmation MUST identify whether consent is:

- `THIS_SESSION_ONLY` — the default; held in process memory and discarded at
  normal shutdown, crash recovery, or application restart; or
- `REMEMBER_SOURCE` — an explicit additional choice that permits the trusted
  Python semantic backend to persist the canonical source identity for later
  sessions.

No remembered-source field may be stored in browser localStorage. Remembered
consent MUST NOT weaken the separate per-turn inclusion gate. Rust owns native
picker and path mediation and issues opaque source handles; Rust does not own or
persist semantic source consent.

### 4.2 Per-turn inclusion consent

For every turn that requests Project Knowledge, LocalComet MUST prepare a bounded
preview before a model call. The preview MUST show the exact context text,
relative provenance, source count, `vault_revision`, truncation state, and an
immutable preview digest.

The user must choose exactly one action:

- `INCLUDE_AND_SEND` — send the exact approved preview with the turn;
- `REJECT_AND_SEND_WITHOUT_KNOWLEDGE` — send the turn without source content; or
- `CANCEL` — cancel the turn without a model call.

There is no remembered per-turn approval, bulk approval, implied approval,
approval by chat text, or automatic include mode in the first implementation.

These two Project Knowledge consent gates are distinct from Knowledge Change
Review and Review Center decisions. A Review Center decision does not create
source consent, remembered consent, filesystem authority, or per-turn inclusion
consent, and none of those authorities may be inferred from review approval.

## 5. Revocation

Settings MUST provide `Disconnect and forget source` whenever a source is active
or remembered. Revocation MUST be explicit, idempotent, and available without a
working model.

On revocation, LocalComet MUST:

1. stop admitting new scans, refreshes, previews, and inclusion decisions;
2. increment the source generation, cancel active source work, and join it within
   exactly 5 seconds;
3. invalidate pending previews and `vault_revision` identities;
4. clear the in-memory index, excerpts, decisions, and source path;
5. remove any Python-owned remembered-source record;
6. emit only a sanitized terminal state; and
7. leave every source file and directory unchanged.

Every scan, refresh, preview, and result MUST carry the generation captured when
the operation was admitted. A result is accepted only when its generation still
equals the active consent generation. Closing admission and incrementing the
generation occur before cancellation. Any result delivered afterward is
discarded without changing state, even if the underlying operation reports
success. Failure to join within 5 seconds is `REVOCATION_INCOMPLETE`, leaves
Project Knowledge disabled, and is an acceptance failure; it never permits a
late result to become active.

Revocation cannot retract context already delivered to a running or completed
local model turn. The UI MUST state this before confirming revocation when such a
turn exists. After revocation, no retry may reuse the prior context.

## 6. Read-only filesystem boundary

The selected source MUST be one existing absolute directory on a fixed local
volume. The following candidates MUST be rejected:

- relative, empty, drive-relative, device, UNC, network-share, or URL forms;
- a volume root, user-profile root, Windows directory, Program Files root,
  temporary-directory root, LocalComet install directory, or LocalComet AppData
  root;
- a file instead of a directory;
- a root that is itself a symlink, junction, mount-point redirection, or other
  reparse point; and
- a root whose ancestor chain cannot be validated without crossing a reparse
  point.

All reads MUST remain beneath the canonical selected root. The application MUST
use directory enumeration and file-open operations that do not follow links.
Absolute paths MUST stay inside trusted backend memory. The frontend and model
may receive only relative paths proven to remain within the source.

The selected directory MUST satisfy the LocalComet Vault v2 schema enforced by
the validator at baseline commit
`a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`. Indexable content is limited to
regular Markdown files with the `.md` extension.

The only auxiliary file contents authorized for structural validation are:

- regular `*.base` files beneath the selected root; and
- `00 Канон/LocalComet — Архитектурная карта.canvas`.

Regular `.obsidian/*.json` entries may be counted and inspected as directory
metadata, but their contents MUST NOT be opened or read. Auxiliary content MUST
NOT enter retrieval results or model context. Expanding the Vault version,
supported extensions, auxiliary paths, or auxiliary content rules requires a
new authority decision.

LocalComet MUST NOT create, write, append, truncate, rename, move, delete, copy,
touch, lock, chmod, set attributes, set extended metadata, or repair anything in
the source. Validation errors are reported; they are never fixed automatically.

## 7. Symlink, reparse-point, and race protection

The root, every traversed directory, every candidate file, and every referenced
relative component MUST be inspected without following links. Every symlink,
junction, mount point, reparse point of any tag, and cloud placeholder within the
traversed source is a hard failure for that scan. The first implementation has no
safe-reparse or safe-cloud-placeholder exception.

For each file, LocalComet MUST:

1. validate the parent chain beneath the canonical root;
2. inspect the entry without following links;
3. open it in no-follow/read-only mode;
4. verify after opening that type, identity, and containment still match; and
5. reject the complete candidate index on any time-of-check/time-of-use change.

No partial index may become active. A path that disappears, changes identity,
changes type, or becomes a reparse point during a scan is a safe refresh failure.
If the platform cannot provide no-follow open and post-open type, identity, and
containment verification, LocalComet MUST reject the scan. Following the path or
using a weaker check is not an allowed fallback.

The current KnowledgeAdapter and Vault v2 validator use path-based reads and do
not yet satisfy this handle-level rule. They are not production-conforming and
MUST NOT be wired to a production source until a separately authorized
implementation hardens them and passes the required tests.

## 8. Persistence and lifecycle

The outer source-selection lifecycle is:

```text
NOT_CONFIGURED → AWAITING_CONFIRMATION → VALIDATING → READY
READY → REFRESHING → READY
READY|REFRESHING|ERROR|DEGRADED → REVOKING → NOT_CONFIGURED
AWAITING_CONFIRMATION|VALIDATING|REFRESHING → ERROR
```

This outer lifecycle does not rename the existing Python `AdapterState`
contract. Its projection is:

| Outer source state | Existing `AdapterState` projection |
|---|---|
| `NOT_CONFIGURED` | `NOT_CONFIGURED` |
| `AWAITING_CONFIRMATION` | `NOT_CONFIGURED` (adapter not admitted) |
| `VALIDATING` | `SCANNING` |
| `READY` | `READY` |
| `REFRESHING` | `SCANNING` |
| `DEGRADED` | `DEGRADED` |
| `ERROR` | `ERROR` |
| `REVOKING` | `NOT_CONFIGURED` (new adapter work not admitted) |

`vault_revision` remains the existing Python and desktop wire field. The phrase
"source revision" is descriptive prose only and MUST NOT rename that field.

`THIS_SESSION_ONLY` stores the path, index, and consent only in trusted process
memory. `REMEMBER_SOURCE` MAY persist only the minimum Python-owned semantic
record: contract version, canonical path, opaque source ID, sanitized display
name, consent timestamp, and last validated `vault_revision`. It MUST NOT persist
note text, excerpts, prompts, previews, or absolute paths in frontend storage.
Rust may reconstruct and validate an opaque source handle from the Python-owned
record but MUST NOT persist a second semantic consent record.

A remembered source MAY be validated at application startup because the user
explicitly chose persistence. Startup failure MUST leave chat usable and Project
Knowledge unavailable. It MUST NOT retry indefinitely or block application
readiness beyond the 30-second scan budget. Startup cancellation and revocation
remain subject to the exact 5-second join deadline.

The in-memory index is replaced atomically only after a complete successful
validation. Shutdown clears all session-only state. Crash recovery treats any
unfinished scan or preview as invalid.

## 9. Scan limits

The first implementation MUST enforce limits no greater than:

| Resource | Hard limit |
|---|---:|
| Active sources | 1 |
| Traversal depth below source root | 32 directories |
| Inspected filesystem entries | 10,000 |
| Markdown notes | 2,000 |
| Bytes per Markdown note | 1,048,576 |
| Aggregate Markdown plus auxiliary content bytes read per scan | 67,108,864 |
| Bytes per permitted auxiliary file | 1,048,576 |
| Query characters | 4,096 |
| Results exposed to desktop preview | 8 |
| Selected sections per note | 3 |
| Characters per excerpt | 1,200 |
| Total preview context characters | 12,000 |
| One scan or refresh wall-clock budget | 30 seconds |

Lower operational defaults are allowed. Raising a hard limit requires a reviewed
contract change and corresponding denial tests.

The aggregate byte counter MUST include every Markdown, `*.base`, and authorized
canvas content byte read. Before each content open, the candidate's size MUST be
checked against the remaining aggregate budget. Metadata inspection does not
authorize opening unlisted auxiliary content.

## 10. Refresh and freshness rules

There is no continuous watcher, periodic scan, launch-time download, or hidden
background refresh. Refresh occurs only:

- immediately after confirmed source selection;
- at startup for an explicitly remembered source;
- when the user activates `Refresh`; or
- as a bounded freshness check before an approved preview is injected.

Every successful scan produces a deterministic `vault_revision`. A preview is
bound to the source ID, `vault_revision`, turn ID, selected content hashes, and
preview digest. If any identity or the active source generation changes before
inclusion, LocalComet MUST reject the decision, invalidate the preview, and
require a fresh preview.

A failed refresh MUST NOT activate a partial candidate. The previous validated
index MAY remain in memory for diagnostics, but it is `DEGRADED` and MUST NOT be
used for a new preview until a complete refresh succeeds.

## 11. Redaction and failure behavior

Logs, IPC errors, telemetry, and diagnostics MUST NOT contain absolute paths,
source text, note bodies, excerpts, prompts, secrets, credentials, environment
variables, or raw exception representations.

Safe diagnostics MAY contain bounded error codes, operation state, elapsed time,
counts, byte totals, relative paths when needed for user remediation, and
cryptographic digests. A displayed relative path MUST first pass containment and
control-character validation.

Secret-like content detected by the approved validator MUST be reported as a
redacted blocking finding. The matching secret value MUST NOT be repeated in the
UI or logs. Raw source content appears only in the local preview required for
per-turn consent.

All boundary, validation, timeout, cancellation, stale-revision, and malformed
content failures are fail-closed:

- no source content is sent to a model;
- no partial index becomes active;
- no automatic fallback silently sends a knowledge-enabled turn;
- ordinary chat remains available through an explicit send-without-knowledge
  path; and
- the source remains unchanged.

## 12. Data ownership and deletion

The user owns the selected source. LocalComet owns only its Python-owned semantic
consent record, opaque identifiers, in-memory index, and sanitized diagnostics.
Revocation may delete LocalComet-owned configuration and volatile state but MUST
NOT delete or modify source content.

Normal application uninstall continues to preserve user-owned data under the
existing installer contract. Any future UI for deleting remembered Project
Knowledge configuration requires an explicit, separate user action and may not
be coupled to source deletion.

## 13. Phase B0 completion boundary

Phase B0 is complete when this authority contract, its threat model, test and
acceptance plan, and rollback plan are internally consistent and pass repository
documentation checks. Completion does not make Project Knowledge available in
the installed product, reopen Phase A, or supersede the existing OR-01
prohibition on Vault access, new IPC/capabilities, or implementation work. Any
future code or capability work still requires separate owner authorization.
