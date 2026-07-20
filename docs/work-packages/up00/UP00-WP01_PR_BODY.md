# UP00-WP01 — Windows one-click launch and installer baseline

> Draft prepared locally for human review. Do not push or create a remote pull request from this work package.

## Purpose

Package LocalComet as a per-user Windows desktop application that starts its existing managed backend automatically, waits for bounded readiness, handles duplicate launch safely, and shuts down without orphan processes.

## User-visible result

After one NSIS installation, the user starts `LocalComet` from the Start Menu or desktop. No terminal, repository checkout, Python, Node.js, npm, Cargo, Vite, or Tauri CLI is needed for installed launch.

## Exact scope

- Prospective governance/owner-decision records for this work package.
- Existing-sidecar runtime packaging and Windows NSIS configuration.
- Main/child no-console behavior.
- Bounded startup readiness, native startup failure, single-instance behavior, and process shutdown.
- Installer, shortcut, lifecycle, uninstall, negative-authority, and rollback verification.

## Exclusions

No IPC/schema/data-lifecycle redesign, UI redesign, model manager, Review Center, Prompt Studio, autonomous tasks, publication, approval mutation, Vault action, telemetry, updater, signing infrastructure, broad dependency upgrade, or UP01-UP10 implementation.

## Architecture decisions used

- `OR-01` prospective Architecture Governance Pack/Constitution ratification.
- Source Mapping `COMPLETED_AND_REMEDIATED` at `6c784ace543e345bdb8bd2f778be974dc89f2df5`.
- Existing Svelte static UI, Tauri 2 Rust boundary, framed pipe IPC, Python sidecar, Windows Job Object containment, LocalComet metadata/icon, and per-user app-data convention.

## Deferred decisions untouched

G03/G12 decomposition, G05 IPC versioning, G09 data lifecycle, public licensing, production performance baselines, production signing, and automatic updates.

## Files changed by category

To be completed from the final file-operation manifest.

## Installer artifact

To be completed with final filename, byte size, SHA-256, installed executable identity, and `UNSIGNED_INTERNAL_BUILD` classification.

## Tests and evidence

To be completed with exact frontend, Python/backend, Rust/Tauri, installer, installed-launch, shortcut, lifecycle, uninstall, authority-negative, and rollback results.

## Rollback

Uninstall without optional app-data deletion, preserve `%LOCALAPPDATA%\LocalComet`, and revert only this branch's commits in a disposable local clone. Never use rollback to delete user data or modify the Vault.

## Known limitations

- Unsigned internal build only.
- No production code signing or automatic updates.
- No public-release licensing or distribution claim.
- System WebView2 is a prerequisite; the installer adds no network bootstrap.

## Reviewer checklist

- [ ] Governance commit is documentation-only and precedes source changes.
- [ ] Only UP00-WP01 is authorized and implemented.
- [ ] Existing IPC, data ownership, and architecture boundaries remain unchanged.
- [ ] Installer is current-user and installer files do not overlap user data.
- [ ] Both shortcuts target the installed executable.
- [ ] Readiness, duplicate launch, shutdown, failure cleanup, and no-console evidence pass.
- [ ] Uninstall removes installer ownership and preserves user state.
- [ ] Frontend, Rust/Tauri, backend, negative-authority, and rollback checks pass.
- [ ] Artifact/evidence manifests and checksums verify.
- [ ] `main` is unchanged; no push or remote PR occurred.

**Release warning:** `UNSIGNED_INTERNAL_BUILD`
