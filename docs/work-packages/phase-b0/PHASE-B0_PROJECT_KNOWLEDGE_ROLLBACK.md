# Phase B0 — Project Knowledge Rollback Plan

Status: `DOCUMENTATION_CONTRACT_ONLY`

This plan defines rollback for the Phase B0 documentation and the minimum
rollback obligations for any later Project Knowledge implementation. Phase B0
itself creates no runtime state and does not access a knowledge source.

## 1. Rollback invariants

Every rollback MUST:

- preserve the user-selected source byte-for-byte;
- avoid the user's Obsidian Vault, normal AppData, installed application, and
  historical repository unless a later, explicit rollback authorization names
  an isolated test target;
- avoid `reset --hard`, `clean`, stash-based loss, or deletion of unrelated work;
- remove no model, managed runtime, conversation, project, or user file;
- restore truthful Project Knowledge UI state;
- leave ordinary local chat and the Phase A model lifecycle functional; and
- produce reviewable repository and runtime evidence.

## 2. Phase B0 documentation rollback

Before any future commit, the Phase B0 change is only four untracked Markdown
files. If the owner rejects the contract, stop and request explicit direction;
do not remove files automatically.

After a future documentation commit, rollback is additive. Preserve these four
documents and add a reviewed supersession or revocation record that identifies
the affected contract version and commit, the reason, the effective status, and
any replacement authority. The original files remain historical evidence and
must not be removed, emptied, or rewritten to conceal their prior authority.

Deleting any Phase B0 documentation file requires explicit owner authorization
that names each file and explicitly overrides the repository no-delete rule. A
generic request to roll back, revert, disable, or supersede Phase B0 is not file-
deletion authority. History must not be rewritten and the Build Week tag must
not move.

Documentation rollback verification:

```powershell
git diff --check
git --no-pager status --short --untracked-files=all
git --no-pager log -5 --oneline --decorate
```

Run the explicit trailing-whitespace and final-newline check from the test and
acceptance plan over these four documents and any additive supersession record.
After an authorized staging action, also run `git diff --cached --check`.

Because Phase B0 changes no product code or runtime state, no Python, npm, Cargo,
installer, AppData, or installed-application rollback action is required.

## 3. Future implementation rollback triggers

Any later Project Knowledge implementation must be held or rolled back if one of
these occurs:

- source content, metadata, attributes, names, or write times change;
- a path escapes the selected root or any reparse point or cloud placeholder is
  accepted;
- anything beyond root type, root reparse status, fixed-volume identity, and a
  sanitized display name is inspected before consent;
- source content is read before consent or after revocation;
- a repository or project root is defaulted, inferred, or inspected without
  separate explicit project-root consent;
- external `source_paths` are resolved or opened without that separate consent;
- source content reaches a model without exact preview approval;
- a stale, altered, partial, or replayed preview is accepted;
- absolute paths, source text, prompts, or secrets appear in logs or frontend
  payloads;
- a failed refresh remains usable for new previews;
- persisted consent cannot be revoked completely;
- semantic consent is persisted outside Python or duplicated by Rust;
- cancellation work does not join within 5 seconds or a prior-generation result
  becomes active;
- ordinary chat becomes unavailable when Project Knowledge fails;
- the implementation adds generic filesystem, shell, network, process, or raw
  IPC authority;
- packaged acceptance touches a normal-profile Vault or AppData root; or
- regression, security-negative, installer, shutdown, or orphan checks fail.

## 4. User-initiated operational rollback

The primary runtime rollback is `Disconnect and forget source`. It must work even
when validation, the model, or the source is unavailable.

The sequence is:

1. close admission for new source operations;
2. increment the source generation;
3. cancel active scan/refresh/preview work and join it within exactly 5 seconds;
4. reject every result carrying the prior generation;
5. invalidate preview, `vault_revision`, and per-turn decision identities;
6. clear the in-memory index, excerpts, and source path;
7. remove Python-owned remembered consent;
8. set state to `NOT_CONFIGURED`;
9. keep ordinary chat available; and
10. verify the source was not modified.

If configuration removal fails, Project Knowledge remains disabled and reports a
sanitized `REVOCATION_INCOMPLETE` state. It must not resume source reads on the
next launch. The user receives bounded remediation guidance that never includes
the absolute source path.

Missing the 5-second join deadline has the same fail-closed result. The prior
generation remains permanently rejected, Project Knowledge remains disabled,
and operational rollback is incomplete until acceptance evidence proves no
source worker remains.

## 5. Source-code rollback for a future implementation

Source rollback must occur only on a clean, authorized feature branch. Use
reviewable revert commits in reverse dependency order:

1. production UI enablement and source-selection controls;
2. frontend bridge/store/type changes;
3. Tauri permissions and narrow Rust command changes;
4. Rust picker, opaque-handle, and path-boundary implementation;
5. Python production adapter, semantic consent persistence, and lifecycle
   integration;
6. implementation tests; and
7. implementation documentation, leaving this Phase B0 authority record unless
   the owner separately revokes it.

Do not restore the prior environment-variable-only prototype as a production
configuration path. A rolled-back build must truthfully show Project Knowledge
as unavailable and must ignore, without deleting, any later-version remembered
record it cannot safely interpret.

## 6. Persisted-state compatibility

Rollback must not require reading the selected source. The older application may
leave a later-version Python-owned semantic consent record untouched, but it
must not activate or display it as configured. Reinstalling a compatible future
build may offer to revalidate it only after confirming the record version and
consent.

Deleting a remembered consent record is authorized only by user revocation or a
separately approved migration. Under no condition may cleanup delete the source
directory or any descendant.

Frontend localStorage must never contain the absolute source path, so UI rollback
requires no path cleanup. Any discovery of such a value is a security incident:
disable Project Knowledge, preserve bounded evidence, and request explicit
remediation authority.

## 7. Package and installed-build rollback

Future packaged rollback must use an isolated application-data root and a
disposable fixture source. The sequence is:

1. record fixture and isolated-profile manifests without source content;
2. revoke Project Knowledge in the current build;
3. close LocalComet and prove no scan, sidecar, app, or model-runtime orphan;
4. uninstall through the canonical uninstaller without deleting user data;
5. install the last accepted package;
6. confirm Project Knowledge is unavailable and ordinary chat still works;
7. close normally and recheck process state; and
8. compare the fixture manifest byte-for-byte; and
9. use the required ProcMon or equivalent ETW process-tree audit to confirm no
   protected normal-profile Vault or AppData root was opened.

Installer rollback must preserve the existing unsigned-internal-build and
current-user boundaries. It must not introduce a network bootstrap, updater,
service, scheduled task, or data-deletion option.

## 8. Rollback acceptance evidence

Required evidence for a future implementation rollback:

- exact source commits and revert commits;
- changed-file list with no unrelated path;
- focused consent, containment, reparse, redaction, refresh, and revocation tests;
- complete supported frontend, Rust, Python, sidecar, and package checks;
- isolated fixture pre/post manifest showing zero mutation;
- isolated profile identity and a sanitized ProcMon or equivalent ETW
  process-tree report proving zero matching opens under protected normal-profile
  Vault and AppData roots;
- process inventory showing no orphan;
- `git diff --check`; and
- final clean worktree status.

The access audit must use the same process-tree, path-prefix, operation, capture-
interval, protected-path handling, and evidence-redaction rules defined by the
test and acceptance plan. If that audit is unavailable, rollback package
acceptance remains incomplete.

Evidence must exclude absolute personal paths, note bodies, prompts, secrets,
environment dumps, source copies, screenshots containing source content, and
model responses containing approved knowledge.

## 9. Stop conditions

Stop rollback and request owner direction if:

- the target commit or installed package cannot be identified exactly;
- the worktree contains unrelated changes that overlap rollback paths;
- rollback would require deleting or migrating user data;
- documentation rollback would require deleting a Phase B0 file without the
  owner's explicit named-file override;
- source preservation cannot be proven without accessing a non-isolated source;
- a remembered record requires an undecided schema/data-lifecycle migration; or
- the last accepted package cannot truthfully represent Project Knowledge as
  unavailable.

Rollback completion means the product no longer uses Project Knowledge, ordinary
local chat remains functional, the selected source is unchanged, no managed
process remains, and repository state is reviewable.
