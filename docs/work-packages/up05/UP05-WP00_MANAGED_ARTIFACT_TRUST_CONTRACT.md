# UP05-WP00 Managed Artifact Trust Contract

<!-- Source-controlled trust decision. -->

Status: implementation contract approved; bootstrap identities pending bounded acquisition.

Depends on UP01-WP01 at 0467cf71e1cf0e0400d687c1829e7bd0de91eebc. Completion unblocks UP05-WP01 model/chat reliability work; it does not complete chat reliability itself.

## Trust root

LocalComet approval authority consists only of:

1. the reviewed source file desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json;
2. the strict Rust parser and validator compiled into the packaged desktop application;
3. the packaged LocalComet application that embeds the exact catalog bytes;
4. exact lowercase SHA-256 identities over raw upstream artifact bytes.

The catalog is immutable at runtime. Frontend, model output, Python sidecar, AppData, installed inventory, and local files cannot add or override approval. Updating approval requires a source commit, review, new application build, and installer.

## Catalog versus installed state

The catalog answers what may be trusted. Installed state answers whether an approved artifact is currently present and byte-valid.

Installed state is derived live from catalog-declared relative paths under the source-grounded LocalComet per-user roots:

- runtimes/llama.cpp below the LocalComet application-data root;
- models below the LocalComet application-data root;
- runtime-state for private ephemeral process state only.

WP00 deliberately does not create a persistent installed-artifacts cache. Live derived snapshots avoid a second state file, remain reconstructible, and prevent AppData from becoming approval authority. A future cache may be added only under the mission's non-authoritative reconciliation rules.

## Resolution chain

Every managed launch must resolve:

stable model ID
→ approved model catalog entry
→ exact contained managed model path
→ byte count, SHA-256, and GGUF validation
→ approved compatible runtime ID
→ exact contained runtime package
→ required file byte counts and SHA-256
→ fixed LocalComet launch policy

Raw frontend paths, arbitrary AppData records, arbitrary executables, and arbitrary arguments are never inputs to this chain.

## Canonical identity

Artifact IDs are explicit lowercase ASCII identifiers, unique by kind and immutable after publication.

Bootstrap IDs:

- llama-cpp-windows-x86-64-cpu-bootstrap
- qwen2.5-1.5b-instruct-q4-k-m

The catalog is UTF-8 without BOM, LF-only, deterministically ordered, duplicate-key-free, without trailing whitespace, with exactly one terminal newline. Its catalog digest is the SHA-256 of those exact file bytes.

Artifact hashes are SHA-256 over exact raw upstream artifact bytes. Extracted runtime file hashes are separately pinned as required-file identities.

## Managed containment

Catalog paths are relative and use forward-slash components. Validation rejects absolute paths, drive-relative paths, backslashes, empty components, dot components, traversal, NUL, reparse points, and paths outside the approved root after resolution.

Runtime executable identity is catalog-controlled and must remain within its approved runtime package. Model identity must remain within the model root and must satisfy exact size, SHA-256, .gguf extension, and GGUF magic checks.

## Typed read-only contract

Tauri exposes only bounded safe projections:

- approved runtime catalog;
- approved model catalog;
- live validated installed artifact statuses;
- one artifact validation status by stable ID;
- one model compatibility/readiness result by stable model ID.

No typed command accepts catalog JSON, paths, URLs, commands, environment variables, approval flags, or inventory writes. Existing managed start continues to accept only a stable model ID and revalidates the full chain in Rust.

## Approval update process

1. Resolve one owner-authorized artifact from its official upstream.
2. Download outside the repository and Vault.
3. Validate source identity, bytes, SHA-256, format/archive safety, and license.
4. Add exact metadata to the canonical catalog in stable ID order.
5. Run strict schema, canonical serialization, path, compatibility, and negative-security tests.
6. Review and commit source.
7. Build a new application/installer before the approval can take effect.
8. Provision the exact pinned bytes only into catalog-declared application-owned paths.

No runtime automatic download is added.

## Explicit non-authorities

The following cannot approve an artifact:

- AppData files or caches;
- filenames or filesystem metadata;
- model output;
- frontend state;
- Python sidecar responses;
- local HTTP responses;
- process existence or port availability;
- unsigned URLs, redirects, ETags, or archive listings;
- installer presence without exact catalog validation.

## Bootstrap limitations

The Qwen bootstrap model is for internal inference validation, Russian/English smoke tests, and protocol verification. It is not a production default, public-distribution payload, installer payload, automatic-download target, recommendation for every machine, quality baseline, or performance baseline.
