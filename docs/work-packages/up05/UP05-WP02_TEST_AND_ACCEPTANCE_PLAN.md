# UP05-WP02 — Test and Acceptance Plan

## Automated source verification

Focused Rust tests cover canonical acquisition metadata, confirmation and
unknown-ID rejection, HTTPS/redirect-host enforcement, GGUF magic validation,
runtime ZIP traversal/case-collision/hash rejection, owned partial cleanup,
valid-artifact reuse, conflicting-artifact rejection, duplicate-job handling,
and terminal-state immutability. They create only temporary test directories
and make no external network request.

Frontend tests prove the bridge accepts no URL, destination, hash, header,
generic HTTP, or generic filesystem arguments; reject malformed projected job
states; and keep Settings and first-use actions bounded. Existing managed
artifact and chat lifecycle tests continue to run.

## Installed acceptance gate

The required isolated-root acquisition acceptance remains mandatory: acquire
the catalog-approved runtime and model, validate, connect, obtain two real
responses, Stop/Retry, cancel an in-progress model transfer, remove the
disconnected model, and redownload it. The installed runtime/model in the user
root must not be touched.

As of the current source checkpoint, that gate cannot start because the normal
Tauri build stops before compilation: the baseline checkout is missing
`binaries/localcomet-core-x86_64-pc-windows-msvc.exe`, which the package
configuration requires. The isolated source-level checks use a temporary Tauri
configuration override only to validate Rust code; it is not evidence of a
bundle, installer, network-acquisition, or chat acceptance pass.
