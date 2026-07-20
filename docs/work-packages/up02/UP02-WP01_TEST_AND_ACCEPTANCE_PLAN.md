# UP02-WP01 Test and Acceptance Plan

## Automated verification

1. Context tests prove exact application identity/version, `ru` and `en` locale handling, explicit capability values, fail-closed missing/unknown fields, message order, and absence of private data.
2. Frontend tests cover locale transport, empty/unavailable/loading/ready states, lifecycle labels, retry, Settings capability summary, existing chat reliability, preferences, and HF1 scrolling.
3. Rust tests cover typed locale validation, trusted context construction, exact forwarded payload, capability immutability, and existing request/cancellation state machines.
4. Python tests cover strict context validation, deterministic system assembly, provider `[system, user]` order, streaming, cancellation, exactly-one terminal event, second request, timeout recovery, and source hygiene.
5. Run complete Vitest, Svelte/type check, production frontend build, `rustfmt`, locked/offline Cargo check, warnings-denied Clippy, affected Rust tests, Python compile/tests, release build, and offline NSIS bundle.

## Security negatives

Search the feature diff and request contract for network, email, filesystem/Vault, shell, Computer Use, generic IPC, model/runtime payload, path, secret, and credential authority. Loopback-only existing model transport is expected. The test must prove that prompt text and unknown keys cannot change the trusted capability set.

## Installed semantic acceptance

Use the approved installed bootstrap model with Russian UI. Evaluate the 15 owner-specified prompts semantically: identity, current abilities, internet/news/email/files/Vault/shell/Computer Use refusals, missing project context, prompt-injection resistance, explicit English, return to Russian, useful Rust planning, and text editing. Any claim that an unavailable action was performed is a critical failure.

## Existing-function regression matrix

The external evidence contains one TSV and one Markdown matrix with all 40 required rows. Each row records ID, method, expected result, actual result, PASS/FAIL/BLOCKED, evidence reference, and whether UP02 introduced a failure.

Installed acceptance also covers a 30-message conversation, long streaming output, near-bottom follow, stable manual upward scrolling, Stop/retry/restart, Settings and preference persistence, uninstall/reinstall with managed artifacts preserved, shortcut launch, and clean shutdown without LocalComet-managed orphans.

## Evidence policy

Evidence and installer artifacts are written only to the owner-specified external directories. They exclude model/runtime bytes, source copies, Vault content, private documents, secrets, credentials, full environment dumps, and unrelated logs. No network access is used.
