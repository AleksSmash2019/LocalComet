# UP05-WP02 Phase A final checkpoint

Status: `PASS_LC_PE01_PHASE_A_COMPLETE_CHECKPOINTED`

LC-PE01 Phase A is complete and checkpointed. Phase B Project Knowledge has
not started and remains outside this checkpoint.

## Repository checkpoint

- Branch: `feat/up05-wp02-approved-model-manager`
- Pre-checkpoint HEAD: `573434dd4a35250758fc65168929042e37fc48b4`
- `main`: `6c784ace543e345bdb8bd2f778be974dc89f2df5`
- `origin/main`: `6c784ace543e345bdb8bd2f778be974dc89f2df5`
- Tracked worktree and index were clean before this documentation file.
- The established generated sidecar tree under
  `desktop/localcomet-desktop/src-tauri/binaries/` remains untracked and is
  deliberately excluded from the checkpoint.

## Complete UP05-WP02 commit chain

1. `32b7a1834b423adfcaba417015c59c6ebc58c330` — `docs(up05): define approved acquisition and model manager`
2. `7381bf2f4340574891dcd8a3ae84f493298cd42e` — `feat(model): add approved artifact acquisition contract`
3. `79b78625c7db059679eabb26e439423032f83a59` — `feat(model): implement verified atomic artifact installation`
4. `94d0f354ab3b2b34ed10f8d4d7bb105c522182c9` — `feat(settings): add basic local model manager`
5. `c99dfc4f182a4b548599f9ea869293a609ea39bf` — `test(model): validate downloader and model-manager boundaries`
6. `46762ff3eafd6169f2dc9dfad30bc44694bc1fb7` — `docs(up05): record phase A verification blocker`
7. `c0a60d1ba3d228c8cea31c1724bec190be9256c1` — `fix(storage): unify packaged application data root`
8. `3c7bc0df6c150e204c6d76920cc62f2823d42c3f` — `docs(up05): record packaged profile isolation fix`
9. `38e64b3a9349a27d9b0df108bf1e4beda23ca3de` — `fix(catalog): allow exact approved Hugging Face redirect`
10. `7874a44995031767694dadeaf97a656e2ce5278b` — `docs(up05): checkpoint redirect fix pending packaged smoke`
11. `051801b9223438fc908a1f3297cd8fbf7ec1f893` — `fix(acquisition): persist bounded terminal failure diagnostics`
12. `e53393f60ca19c8d3a8a28cd3d57e5d06affa121` — `docs(up05): record runtime diagnostics checkpoint`
13. `4d135e07529f1d7e6dce459a7167f62080addf09` — `legal(runtime): add pinned llama.cpp MIT license asset`
14. `eaf20ceee2a76c8478562cd9c05890c189321214` — `fix(runtime): enforce exact archive envelope`
15. `3904b3aa6aa4e996f09a04176e8f0e0dd631a3e4` — `docs(up05): record runtime archive envelope`
16. `573434dd4a35250758fc65168929042e37fc48b4` — `fix(packaging): align startup-log scan with app-data root`

## Source, test, and package gates

- The immutable catalog owns the exact model/runtime URL, redirect allowlist,
  expected filename, byte count, SHA-256, and managed destination. The
  frontend supplies only a fixed artifact ID and explicit confirmation.
- The backend enforces HTTPS and exact redirect-host equality, bounded
  streaming, cancellation, expected size and SHA-256, runtime ZIP envelope
  validation, staging, same-volume atomic promotion, live post-install trust,
  and owned cleanup.
- `LOCALCOMET_APP_DATA_ROOT` is the single packaged startup, acquisition,
  model, runtime, and runtime-state root. Empty, relative, and UNC overrides
  fail closed.
- The latest complete Rust suite passed `103` tests, with the two intentional
  offline/bootstrap tests ignored. The real verified b10068 ZIP offline test
  also passed against a temporary test destination.
- Frontend verification passed `17` files and `265` tests.
- `cargo check --locked --offline` passed.
- `cargo clippy --locked --offline --all-targets -- -D warnings` passed.
- Svelte check completed with zero errors. The one pre-existing
  `LanguageSwitcher.svelte` listbox `tabindex` accessibility warning remains
  unchanged.
- The production frontend build passed.
- The normal locked/offline NSIS build with the restored generated sidecar
  passed; no package configuration override was used for the accepted
  candidate.
- Final package-source verification passed `234` checks. Its focused
  startup-log scan regressions passed `9` checks; the focused Rust
  app-data-root and startup suites passed `4` and `3` tests respectively.
- `git diff --check` is the final documentation gate before commit.

## Accepted current candidate

- Installer:
  `C:\Users\DNS\Documents\LocalComet\desktop\localcomet-desktop\src-tauri\target\release\bundle\nsis\LocalComet_0.0.0_x64-setup.exe`
- Installer bytes: `13878331`
- Installer SHA-256:
  `d17f84d0cbcb9a0503cc1c1196c80a126bc61565c04170c644b50530fd4c48eb`
- Installed executable:
  `C:\Users\DNS\AppData\Local\Programs\LocalComet\LocalComet.exe`
- Installed executable bytes: `14220288`
- Installed executable SHA-256:
  `97e8aee1806d6c7da18ff365e9f9b04e312d35a90ae989826381d8c0b0d93c51`
- Canonical NSIS uninstaller:
  `C:\Users\DNS\AppData\Local\Programs\LocalComet\uninstall.exe`
- Uninstaller bytes: `69394`
- Uninstaller SHA-256:
  `d8da71baa2cac61513bcd9920f47421bfb10cdae6fc69bfa785118747f030cf8`

## Profile isolation, redirect, and cancellation

The accepted application-data root is:

`C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\Profile\LocalComet`

Packaged launches inherited this exact override. Startup logging, backend
readiness, acquisition, model discovery/removal, runtime discovery, runtime
arguments, API-key state, and cleanup resolved beneath it. No normal-profile
model path appeared in process arguments or isolated logs.

The Qwen URL remains revision-pinned. The exact observed redirect host
`us.aws.cdn.hf.co` was added only to that model entry. HTTPS-only exact-host
tests rejected ports, userinfo, wildcard/suffix/prefix variants, lookalikes,
trailing dots, and IP literals. Operator-assisted packaged transfer reached
non-zero progress, cancellation completed, and no final, partial, temporary,
staging, download, or duplicate payload remained.

Normal-profile directory metadata remained unchanged through every packaged
launch and installer operation. Its model content was never entered, opened,
hashed, loaded, removed, or modified by this work package.

## Runtime archive-envelope acceptance

- Runtime: `llama.cpp b10068`
- Approved archive: `llama-b10068-bin-win-cpu-x64.zip`
- Archive bytes: `18007324`
- Archive SHA-256:
  `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`
- Exact envelope: `51` top-level regular members.
- Install disposition: `30` pinned files.
- Recognized-not-installed disposition: `21` executable members; none was
  extracted, installed, or launched.
- Source-controlled injected license: `LICENSE-MIT.txt`, `1078` bytes,
  SHA-256
  `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`.
- Final runtime inventory: exactly `31` files, zero missing, mismatched,
  unexpected, or nested entries.

Bounded acquisition diagnostics proved the original archive-envelope failure,
cleanup-before/after records, and zero retained payload. The corrected envelope
then passed the synthetic suite, the independently verified real ZIP test, the
packaged runtime retry, and final live trust validation.

## Model lifecycle and local inference acceptance

- Model ID: `qwen2.5-1.5b-instruct-q4-k-m`
- Final model path:
  `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\Profile\LocalComet\models\qwen2.5-1.5b-instruct-q4-k-m\qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Model bytes: `1117320736`
- Model SHA-256:
  `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`

The packaged model connected through the approved isolated `llama-server.exe`
on loopback. Health returned HTTP 200, the model was listed as owned by
`llamacpp`, one non-empty real local response completed, and no non-loopback
inference connection was observed. The operator then disconnected and removed
the model. The final file and managed directory disappeared, no process lock or
partial remained, and the runtime stayed 31/31. A complete approved redownload
promoted the model only after exact size and SHA-256 verification; no duplicate
or acquisition residue remained. The model was left installed and disconnected.

## Current-candidate continuity acceptance

Before the first uninstall, the complete isolated profile contained `43`
entries with signature
`ad3093bb2954a3c5a2f91767b1bfff72ef22417df274c9e1c148ae4c6ed7d0f5`.
The canonical current uninstaller exited `0`; installation files and registry
metadata were removed without touching that profile. The exact current
installer then exited `0`, restored the accepted executable identity, and left
the same profile signature.

The reinstalled candidate recognized both approved artifacts without starting
an acquisition. Operator-assisted connection started the isolated runtime with
the isolated GGUF argument, health returned HTTP 200, and one non-empty local
response completed. No non-loopback inference connection occurred. Disconnect
and normal application closure left no managed process; model/runtime hashes
remained exact.

Result: `PASS_CURRENT_CANDIDATE_UNINSTALL_REINSTALL_CONTINUITY` and
`PASS_POST_REINSTALL_LOCAL_CHAT`.

## Approved HF2 rollback rehearsal

The approved installer-level baseline is linked by its local evidence manifest
to source commit
`408ba67245827889976bf3febf5cf297756127d6` (`build(installer): authorize the
up02 hf2 offline bundle`).

- HF2 installer:
  `C:\Users\DNS\Documents\LocalComet-UP02-WP01-HF2-Artifacts-20260720T221533Z\LocalComet_0.0.0_x64-setup.exe`
- HF2 installer bytes: `12536287`
- HF2 installer SHA-256:
  `9ac01a6218da251b7ec24772320af22de535d68c17e5d8529b01e7d48fb8ca34`
- Observed installed HF2 executable bytes: `10106880`
- Observed installed HF2 executable SHA-256:
  `d2904690353d46ac72c05de282a8e8eadb0dc8de9fcfaa0206fd42cea93abda5`

The evidence manifest did not pre-record an installed executable hash, so the
observed value above is recorded as the result of running the exact
evidence-approved installer. The baseline was not launched because it predates
the confirmed unified profile-root behavior.

After post-reinstall chat, the complete isolated profile signature was
`56087984a114666dd8acce47372c819e01d4ffeecb0fc6ed4aea5a9abca87099`.
It remained identical after current uninstall, HF2 install, HF2 uninstall, and
current-candidate restoration. Both uninstallers and both installers exited
`0`. The restored current executable exactly matched the accepted candidate.

The restored candidate then recognized runtime and model without acquisition.
The final operator check connected only the isolated runtime/model, passed
loopback health, sent no chat, disconnected, and closed normally. No
non-loopback inference connection or acquisition activity occurred.

Result: `PASS_HF2_ROLLBACK_INSTALL`, `PASS_CURRENT_CANDIDATE_RESTORATION`, and
`PASS_FINAL_PACKAGED_CONTINUITY`.

## Final state

- Current candidate is installed.
- Approved runtime remains installed at
  `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\Profile\LocalComet\runtimes\llama.cpp\llama-cpp-windows-x86-64-cpu-bootstrap`.
- Runtime remains exactly `31/31`; all bytes and SHA-256 values match the
  immutable catalog, and none of the 21 skipped executables is present.
- Approved model remains installed at the exact path, byte count, and SHA-256
  recorded above.
- Acquisition entries: `0`.
- Runtime-state entries after closure: `0`.
- Partial/staging/download/backup residue: `0`.
- `LocalComet.exe` processes: `0`.
- `localcomet-core.exe` processes: `0`.
- `llama-server.exe` processes: `0`.

## Authoritative evidence

- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-ProfileIsolation-20260721T011604Z\PACKAGED_PROFILE_ISOLATION_FIX_EVIDENCE.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-PackagedAcceptance-20260721T012950Z\PACKAGED_MODEL_ACCEPTANCE_BLOCKER.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RedirectSmoke-20260721T022326Z\OPERATOR_REDIRECT_SMOKE_EVIDENCE.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\RUNTIME_INSTALL_BLOCKER.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\RUNTIME_DIAGNOSTIC_RETRY_EVIDENCE.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\RUNTIME_ARCHIVE_CONTENT_DRIFT.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\LICENSE_PROVENANCE_BLOCKER.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\RUNTIME_ARCHIVE_ENVELOPE_EXTRACTION_PLAN.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\PACKAGING_SCAN_AND_RUNTIME_RETRY_RESULT.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\PHASE_A_OPERATOR_PACKAGED_MODEL_LIFECYCLE_20260721T054455Z.md`
- `C:\Users\DNS\Documents\LocalComet-UP02-WP01-HF2-Artifacts-20260720T221533Z\CHECKSUMS.tsv`
- `C:\Users\DNS\Documents\LocalComet-UP02-WP01-HF2-Artifacts-20260720T221533Z\ACCEPTANCE.md`

The historical blocker reports are retained because they establish the profile,
redirect, and runtime-envelope failure modes that the final accepted chain
corrected. They do not override the later PASS evidence.

## Boundaries preserved

- No product source changed during installer continuity, rollback, or final
  checkpoint acceptance.
- Installers, installed binaries, model/runtime payloads, logs, screenshots,
  generated sidecar files, and external evidence are not staged or committed.
- `C:\Users\DNS\Documents\LocalAgent` and
  `C:\Users\DNS\Documents\LocalCometVault` were untouched.
- Nothing was merged, pushed, or submitted as a pull request.
- Phase B was not started.

LC-PE01 Phase A is complete and checkpointed.
