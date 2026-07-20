# UP05-WP01 PR Body

Status: local human-review record; no remote pull request is authorized or open.

## Summary

This R2 package repairs the existing approved managed-model connection and real chat lifecycle. It preserves UP05-WP00 artifact authority and the UP01 desktop shell while adding request-scoped typed acceptance, streaming, cancellation, timeout recovery, truthful readiness, and rendered assistant messages.

## Proven pre-change defects

- Managed llama.cpp chat used the stable catalog model ID in the provider POST instead of the validated server alias.
- The worker could emit events before the start response, and Rust forwarded model events outside request sequence/terminal enforcement.
- Real SSE content was stored in `generatedText`, while the chat rendered a separate fixture message collection.
- Manual connected state, composer Stop behavior, cancel acknowledgement, terminal filtering, and timeout recovery could leave false readiness or indefinite busy state.

## Intended bounded changes

- Extend existing typed model command/event payloads with stable request/session/model identity, timestamp, and bounded generation values.
- Use the managed server alias only at the validated provider boundary.
- Enforce response-before-event ordering, strict request event sequencing, one terminal, cancellation precedence, and bounded cleanup.
- Render one assistant message per accepted request and append real non-empty chunks in order.
- Derive chat readiness from approved installed artifacts plus current runtime/model/binding identity.
- Add focused frontend, Rust, Python, runtime, security-negative, installer, and installed acceptance evidence.

## Explicit non-authorities

No Model Library, download, cloud provider, API key, raw path, directory scan, generic shell, generic IPC, RAG, tool execution, agent framework, Vault change, legacy-checkout change, or unrelated navigation/Settings change is included.

## Verification

Pre-implementation artifact validation and direct real loopback inference passed. Full implementation, automated test, bundle, Start Menu, cancellation/restart, security-negative, and rollback evidence will be filled from the final local commits before human review.

## Distribution

- `INTERNAL_BOOTSTRAP_MODEL`
- `UNSIGNED_INTERNAL_BUILD`
- `NOT_PUBLIC_DISTRIBUTION_READY`
