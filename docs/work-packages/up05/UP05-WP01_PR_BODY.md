# UP05-WP01 PR Body

Status: local human-review record; no remote pull request is authorized or open.

## Summary

This R2 package repairs the existing approved managed-model connection and real chat lifecycle. It preserves UP05-WP00 artifact authority and the UP01 desktop shell while adding request-scoped typed acceptance, streaming, cancellation, timeout recovery, truthful readiness, and rendered assistant messages.

## Proven pre-change defects

- Managed llama.cpp chat used the stable catalog model ID in the provider POST instead of the validated server alias.
- The worker could emit events before the start response, and Rust forwarded model events outside request sequence/terminal enforcement.
- Real SSE content was stored in `generatedText`, while the chat rendered a separate fixture message collection.
- Manual connected state, composer Stop behavior, cancel acknowledgement, terminal filtering, and timeout recovery could leave false readiness or indefinite busy state.

## Bounded changes

- Extended existing typed model command/event payloads with stable request/session/model identity, timestamp, and bounded generation values.
- Used the managed server alias only at the validated provider boundary.
- Moved anonymous-pipe delivery outside unrelated request locks, gave it one owner and a two-second non-blocking bound, and retired the sidecar on partial/broken delivery.
- Enforced response-before-event ordering, strict request event sequencing, one terminal, cancellation precedence, and bounded cleanup.
- Rendered one assistant message per accepted request and appended real non-empty chunks in order.
- Derived chat readiness from approved installed artifacts plus current runtime/model/binding identity.
- Preserved runtime capability flags during internal probing and accepted the exact 32-hex managed runtime instance identity.
- Added focused frontend, Rust, Python, runtime, security-negative, installer, and installed acceptance evidence.

## Explicit non-authorities

No Model Library, download, cloud provider, API key, raw path, directory scan, generic shell, generic IPC, RAG, tool execution, agent framework, Vault change, legacy-checkout change, or unrelated navigation/Settings change is included.

## Verification

Frontend 230/230, Rust 74 passed plus 2 expected environment-gated ignored, Python affected suites, changed-file compilation, cargo fmt/check/warnings-denied Clippy, Svelte check/build, sidecar checks, source hygiene, security review, and offline installer build passed. The supplemental legacy stability suite remains 18/20 solely because of two stale checks in untouched Tkinter code.

The installed app connected the approved Qwen model and rendered two consecutive real answers. Stop produced one `cancelled` terminal with stable partial text and no late mutation; retry and process-clean restart both produced another response. The registered-uninstaller rollback preserved exact managed model/runtime hashes and reinstall restored the app. Source reconstruction/reverse-apply evidence proves the exact WP00 rollback target without changing the canonical checkout.

## Distribution

- `INTERNAL_BOOTSTRAP_MODEL`
- `UNSIGNED_INTERNAL_BUILD`
- `NOT_PUBLIC_DISTRIBUTION_READY`

Final internal installer: `LocalComet_0.0.0_x64-setup.exe`, 12,526,459 bytes, SHA-256 `4557672ade41947b3de4356e5ff8b97757643b78fff8ffbfe1e990d3f82ee4ff`.
