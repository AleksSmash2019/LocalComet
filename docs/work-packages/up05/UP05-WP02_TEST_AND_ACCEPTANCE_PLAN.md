# UP05-WP02 — Test and Acceptance Plan

Focused Rust tests cover catalog acquisition validation, unknown IDs, HTTPS and
redirect allowlists, byte/hash/GGUF failures, safe ZIP rejection, containment,
disk-space failure, cancellation cleanup, stale partial cleanup, valid reuse,
conflicting installed artifacts, duplicate jobs, and exactly one terminal state.
Local HTTP fixtures are used only for negative/progress mechanics; final
official-source acquisition remains catalog-only.

Frontend tests prove the bridge has no URL, destination, hash, header, generic
HTTP, or generic filesystem arguments and that Settings exposes only safe
actions. Existing managed artifact and chat lifecycle tests continue to run.

Acceptance uses an isolated app-data root: acquire runtime and model, validate,
connect, obtain two real responses, stop/retry, cancel a separate in-progress
model acquisition, remove only the disconnected model, and redownload it.
The installed runtime/model in the user root are not touched by isolated tests.
