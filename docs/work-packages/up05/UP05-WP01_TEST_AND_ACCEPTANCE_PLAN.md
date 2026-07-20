# UP05-WP01 Test and Acceptance Plan

Status: R2 plan with pre-implementation baseline evidence; implementation results pending.

## Isolation and baseline

- Work only on `feat/up05-wp01-r2-real-model-chat` from `fa664b16c48c0377841dc334b89b2b3868a0249c`.
- Keep `main` and `origin/main` at `6c784ace543e345bdb8bd2f778be974dc89f2df5`.
- Do not move the previous blocked branch.
- Use locked/offline dependency modes and loopback inference only. Do not download or browse.
- Do not access the Vault or legacy checkout.
- Do not place generated reports, model/runtime bytes, credentials, or private paths in Git.

The production ignored artifact-trust test passed for the owner-provisioned bootstrap artifacts. A direct approved runtime/model streaming request produced non-empty content, 16 JSON chunks, 14 content chunks, exactly one `[DONE]`, and no orphan process. Observed timings were 1027.458 ms load, 382.014 ms first content, and 389.777 ms total. They are observations only.

## Frontend gates

- Run all existing Vitest tests.
- Add model-status tests for approved catalog/install/runtime/model/binding agreement.
- Add a pure chat reducer suite for one user/assistant pair, ordered non-empty chunks, partial preservation, and one terminal.
- Prove listener registration completes before submit.
- Prove request/session/model ID filtering, strict sequence, duplicate terminal rejection, late-token rejection, and no old-request contamination.
- Prove acceptance cannot resurrect an early terminal.
- Prove main-composer Stop targets only the active request.
- Prove cancellation acknowledgement, accepted-cancel precedence, acceptance timeout, first-token timeout, inactivity timeout, and retry recovery.
- Prove no submission occurs without truthful model readiness.
- Prove listener teardown/remount does not accumulate listeners or disable later initialization.
- Run Svelte/type check and production frontend build.

## Rust/Tauri gates

- Run `cargo fmt --check`.
- Run locked/offline `cargo check`.
- Run warnings-denied locked/offline Clippy.
- Run all Rust tests and focused typed command/event tests.
- Prove exact request payload fields, bounded generation values, event identity/sequence validation, one terminal, cancellation precedence, registry cleanup, and rejection of late/foreign events.
- Prove managed runtime is single-instance, loopback-owned, model-ready only after exact alias and inference readiness, and cleaned up on stop/drop.
- Prove bounded runtime startup, model load, cancel, log-reader, and shutdown paths.
- Run release build and Tauri NSIS bundle offline.

## Backend/runtime gates

- Run Python compile/static checks for changed files.
- Run existing model gateway, SSE UTF-8, managed runtime, desktop IPC, sidecar supervisor, and control-plane tests.
- Add a managed real/fake integration proving the outbound chat model field uses the validated alias while events retain the stable model ID.
- Prove response/acceptance is serialized before request events.
- Prove request identity validation, one active request, content ordering, empty-chunk handling, `[DONE]`, one terminal, cancellation, timed-out terminal mapping, second request, and shutdown cleanup.
- Re-run direct approved-model validation and real non-empty SSE inference after implementation.

## Security-negative gates

Reject an unknown model ID, tampered installed model, raw path input, unknown runtime ID, request/model mismatch, foreign request event, invalid sequence, duplicate terminal, and LAN endpoint. Static and runtime checks must confirm generic shell, raw IPC, frontend approval mutation, download behavior, and managed artifact bytes in the installer are absent.

## Legacy stability classification

Re-run `russian control panel menu` and `control panel init smoke` directly. Current evidence identifies them as stale assertions against the retired Tkinter tabbed panel and old `v6.02` class/version. The implementation does not touch that panel. Record their exact results; they block only if a changed model/chat dependency causes a new relevant failure.

## Installed acceptance

After all source checks pass:

1. Build the internal NSIS installer from the final R2 HEAD using the existing offline UP00 helper in a clean external local clone. The helper's legacy branch-name guard is satisfied only inside that disposable packaging clone; the canonical R2 branch is never moved.
2. Copy the installer to the required external artifact directory and create checksums, install/setup guidance, and unsigned-internal notice.
3. Verify the package and installed tree contain no approved managed llama.cpp runtime, GGUF, runtime archive, or matching approved artifact hashes. The established private Python sidecar runtime remains an expected application resource.
4. Install current-user, resolve and launch the actual Start Menu shortcut, and inspect the rendered app through the in-app Browser when available.
5. Connect the approved model and record truthful runtime/model readiness.
6. Send `Ответь одним коротким словом: ГОТОВО`; require acceptance, visible non-empty assistant content, one terminal, and stopped generation state.
7. Send a second short prompt without restarting; require a second non-empty assistant response.
8. Start a longer response and press Stop; require terminal cancellation, no late mutation, and a usable next request.
9. Close the application; require no LocalComet-owned runtime orphan. Reopen from Start Menu, reconnect, and obtain another response.
10. Record load, first-token, total duration, chunk count, and terminal state as safe observations only.

## Rollback and closure gates

- Rehearse source rollback by reversing the bounded R2 commits in a clean external local clone and proving the exact WP00 tree.
- Rehearse installed rollback through the exact registered per-user uninstaller while preserving managed app data, then restore the R2 installer if needed for final evidence.
- Confirm feature worktree/index clean, `main` and `origin/main` unchanged, old blocked branch unchanged, nothing pushed, and no pull request opened.
