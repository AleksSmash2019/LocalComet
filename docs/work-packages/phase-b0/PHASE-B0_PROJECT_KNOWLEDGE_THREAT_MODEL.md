# Phase B0 — Project Knowledge Threat Model

Status: `DOCUMENTATION_CONTRACT_ONLY`

This threat model is subordinate to
`PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md`. It defines the security
conditions a later Project Knowledge implementation must satisfy. Phase B0 does
not access a knowledge source or modify product code.

## 1. Protected assets

- confidentiality and integrity of the user-selected source;
- user control over source selection, persistence, refresh, inclusion, and
  revocation;
- integrity of `vault_revision`, source generation, preview, and per-turn
  decision;
- confidentiality of absolute paths, note content, prompts, and credentials;
- LocalComet's frontend/Rust/Python trust boundary;
- availability of ordinary local chat when Project Knowledge fails; and
- the prohibition on source writes and unauthorized external access.

## 2. Trust boundaries

### Svelte frontend

The frontend is untrusted for filesystem authorization. It may request the fixed
selection flow and render sanitized state, but it must not receive absolute
paths, manufacture consent, choose backend paths, or alter preview identities.

### Rust desktop boundary

Rust owns the native picker, path mediation, opaque source handles, path
containment enforcement, process lifecycle, and narrow Tauri commands. Rust does
not own or persist semantic source consent. It must expose no generic filesystem,
shell, process, environment, or raw IPC authority.

### Python sidecar

Python owns deterministic Vault v2 validation, indexing, retrieval,
`vault_revision`, preview construction, semantic state, semantic consent
persistence, and fail-closed errors. It receives a Rust-mediated opaque source
handle through a fixed internal contract, not a path from frontend-controlled
payload text.

### Local model runtime

The model is not trusted to authorize reads or request additional source data.
It receives only the exact preview approved for one turn and cannot browse the
source, resolve paths, call tools, or persist approval.

### Selected source

The first supported source is one valid LocalComet Vault v2 root. Generic
Markdown directories are unsupported. All source names, metadata, frontmatter,
links, and content are untrusted. Local ownership of a file does not make its
contents safe instructions. External `source_paths` are inert provenance unless
a later authority contract and separate explicit project-root consent permit
otherwise.

## 3. Security invariants

1. Before explicit source consent, Rust may inspect only root type, root reparse
   status, fixed local-volume identity, and sanitized display name; no descendant
   is enumerated and no source file content is read.
2. No source content reaches a model before exact per-turn approval.
3. No LocalComet operation writes to the selected source.
4. No accepted path crosses the canonical root or any reparse or cloud-placeholder
   boundary.
5. No failed, partial, stale, or cancelled scan becomes active.
6. No stale or altered preview can be approved.
7. No source error blocks ordinary chat.
8. No absolute path or secret appears in frontend payloads or diagnostics.
9. Revocation stops future source use and clears LocalComet-owned volatile state.
10. Neither source selection nor content expands model, tool, network, or shell
    authority.
11. No repository or project root is inferred, defaulted, resolved, or inspected
    for Vault validation or for an external `source_paths` value.
12. Knowledge Change Review and Review Center decisions grant no source consent,
    remembered consent, filesystem authority, or per-turn inclusion consent.

## 4. Threats and required mitigations

| Threat | Example | Required mitigation | Failure result |
|---|---|---|---|
| Implicit source selection | App guesses a repository, project root, or environment path | Native picker plus separate confirmation; no default/fallback path; default `NOT_CONFIGURED` | No scan |
| Consent confusion | Folder-picker confirmation is treated as full consent | Dedicated `Use this folder read-only` action and separate persistence choice | Candidate discarded |
| Silent model inclusion | Selected notes are appended automatically | Exact local preview and per-turn decision bound to preview hash | Turn waits or sends without knowledge only by explicit choice |
| Path traversal | `..`, absolute path, device path, crafted separator | Canonical parsing, component validation, relative provenance only | Reject source or result |
| Symlink/junction/cloud escape | Any reparse point, known tag, cloud placeholder, or nested junction | Reject every reparse/cloud entry; mandatory no-follow open and post-open verification; no weaker fallback | Reject complete scan |
| TOCTOU replacement | File changes between validation and read | Revalidate type, identity, and containment after no-follow open; `vault_revision`-bound index | Reject candidate index |
| Directory or file bomb | Deep tree, many entries, huge notes or auxiliary files | Depth, entry, note, aggregate Markdown-plus-auxiliary byte, time, and result limits | Bounded error, no partial index |
| Malformed content | Invalid UTF-8, duplicate metadata, control characters | Strict decoding and deterministic schema validation | Reject affected scan safely |
| Prompt injection in notes | Note asks model to ignore policy or use tools | Treat context as quoted untrusted data; no tool capability; fixed system boundary | Model gets no new authority |
| Secret disclosure | API key or private key appears in a note | Blocking secret scan, redacted finding, no raw secret in logs | Preview/inclusion denied |
| Absolute-path disclosure | Exception embeds user directory | Stable safe errors, relative validated paths only | Redacted error |
| Stale preview | Source changes after user reviews content | Source generation, `vault_revision`, content hashes, turn ID, and preview digest checked at inclusion | Require new preview |
| Approval replay | Old approval is reused for another turn | Single-turn immutable identity; terminal decisions are non-reusable | Reject decision |
| Frontend forgery | Compromised UI submits a path or altered preview | Rust/Python recompute authority and identities; narrow typed commands | Reject request |
| Persistence leak | Absolute source path stored in localStorage or semantic consent duplicated in Rust | Python-owned semantic persistence only; Rust path mediation only; no frontend path storage | Configuration error |
| Revocation race | Scan completes while user revokes | Close admission, increment generation, cancel and join within 5 seconds, reject every stale-generation result | Discard late result; release block if join misses deadline |
| Refresh failure reuse | Old index is silently used after a failed refresh | Mark `DEGRADED`; prohibit new previews until successful refresh | Knowledge unavailable |
| Network-share substitution | UNC target changes remotely | First implementation accepts fixed local volumes only | Reject selection |
| Unsupported file smuggling | Binary renamed or embedded in auxiliary file | Vault v2 schema plus the pinned `*.base` and declared-canvas allowlist, regular-file, size, decoding, and aggregate-byte checks | Reject scan |
| Resource starvation | Repeated refreshes or previews overlap | One active source operation, bounded queue, idempotent cancellation | Busy or cancelled state |
| Log exfiltration | Content appears in tracebacks or crash logs | No raw exception serialization; bounded codes and sanitized fields | Safe terminal error |
| Source mutation | Indexer creates cache, lock, or repair files | Read-only handles and no write-capable code path | Security failure and rollback trigger |

## 5. Prompt-injection boundary

Retrieved knowledge is evidence, not instruction authority. The future model
request MUST clearly delimit context from system and user instructions. Content
inside notes cannot:

- approve an action;
- change LocalComet policy or capability state;
- request more files;
- enable tools, browsing, shell, or network access;
- override the user's inclusion decision; or
- suppress provenance and truncation disclosure.

The first Project Knowledge release remains text-only and tool-free. Treating
context as untrusted does not guarantee model compliance, so the absence of tool
and filesystem capability is a required defense, not an optional prompt rule.

## 6. Persistence threats

Remembered consent increases path-disclosure and unintended-startup-read risk.
Therefore persistence is opt-in, Python-owned, minimal, versioned, and
revocable. Rust may reconstruct an opaque source handle but may not persist a
second semantic consent record. The application must not persist note contents
or previews. A record with an unknown version, invalid path, changed root
identity, or missing consent fields fails closed as `NOT_CONFIGURED` or `ERROR`;
it is never repaired by guessing.

Crash recovery must invalidate unfinished operations and approvals. Temporary
index data, if a later design persists any, requires a separate authority
decision and is not authorized by Phase B0.

## 7. Failure and abuse handling

Security failures have bounded stable codes and sanitized explanations. Repeated
failures may apply an in-memory backoff, but they may not create a scheduled
task, service, telemetry event, or permanent lockout. The user can always revoke
the source and continue ordinary chat.

The application must not offer automatic repair, quarantine, deletion, rename,
permission changes, or source migration. Remediation guidance may identify a
validated relative path and issue class without reproducing sensitive content.

## 8. Residual risks

- Reading files may cause operating-system access-time or security-product
  activity even though LocalComet performs no write.
- A local model may repeat approved sensitive context in its response.
- A user can intentionally approve confidential material for a local model turn.
- A fixed local volume can fail or be externally modified during a scan.
- Sanitized folder display names may still be personally identifying; the UI
  should allow a generic label.

These residual risks must be disclosed in acceptance evidence. They do not
permit weakening consent, containment, redaction, or no-write requirements.

## 9. Threat-model acceptance

The later implementation is acceptable only if automated negative tests cover
every invariant and every table row that can be exercised synthetically, and a
packaged test proves selection, preview, rejection, inclusion, refresh,
revocation, restart, and clean shutdown using a disposable valid Vault v2
fixture source. The current path-based KnowledgeAdapter is not production-
conforming until mandatory no-follow open and post-open identity verification
are implemented and accepted under separate authority.

Testing must never use the user's real Obsidian Vault, normal AppData profile,
installed production model data, or historical repository.
