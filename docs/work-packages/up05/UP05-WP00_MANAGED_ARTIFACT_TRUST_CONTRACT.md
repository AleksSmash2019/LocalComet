# UP05-WP00 Managed Artifact Trust Contract

<!-- Source-controlled trust decision. -->

Status: implementation, bounded acquisition, managed provisioning, direct inference, and rollback rehearsal complete.

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

If a future non-authoritative cache is introduced, each update must use a sibling temporary file, validate its schema and catalog references, flush and close the file, atomically replace the prior file using a Windows-supported operation, reread the result, and validate the exact post-write bytes. Failure must preserve the previous valid cache. Every read must still reconcile the cache with the embedded catalog digest and current artifact bytes; deleting or corrupting it must cause safe live reconstruction.

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

The schema version is 1. The catalog is UTF-8 without BOM, LF-only, deterministically ordered, duplicate-key-free, without trailing whitespace, with exactly one terminal newline. Its exact byte digest is:

`e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`

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

## Approved bootstrap record

Runtime:

- upstream: `ggml-org/llama.cpp`;
- release and revision: `b10068` / `571d0d540df04f25298d0e159e520d9fc62ed121`;
- asset: `llama-b10068-bin-win-cpu-x64.zip`, 18,007,324 bytes;
- SHA-256: `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`;
- license: MIT;
- package identity: 31 exact required files, including the approved executable and DLL set.

Model:

- upstream: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`;
- revision: `91cad51170dc346986eccefdc2dd33a9da36ead9`;
- asset: `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes;
- SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`;
- format/quantization/license: GGUF / Q4_K_M / Apache-2.0.

Both artifacts were acquired from their official upstreams, validated before catalog publication, and provisioned by same-volume atomic placement into their catalog-declared LocalComet-owned locations. Post-placement discovery reports both as catalog-approved, installed, hash-valid, contained, mutually compatible, and launchable. No runtime or model bytes were committed or added to installer resources.

## Acceptance outcome

The approved runtime loaded the approved model on loopback and returned `AI` in a real streaming inference. Load-to-listen was 0.953 seconds; first non-empty content arrived after 114.378 milliseconds; total inference time was 123.099 milliseconds. The stream contained three JSON SSE chunks, one non-empty content chunk, and exactly one `[DONE]`. Peak working set was 1,749,966,848 bytes. Graceful Ctrl+C shutdown completed with no owned or orphan runtime process.

Frontend tests passed 211/211; Svelte check completed with zero errors and one pre-existing warning; the production frontend build passed. Rust formatting, check, warnings-denied clippy, all tests, the 55.05-second provisioned-artifact test, and the offline locked release build in 1 minute 10 seconds passed. Python compilation, the v6.84.5.1 managed-runtime checks, and the clean-room model-gateway check passed. Source reverse-apply and physical same-volume artifact move/absence/restore rollback checks passed.

The broader fast stability gate reported 17/19: its two failures are legacy checks in untouched control-panel code. All WP00-affected checks passed.

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

The Qwen bootstrap model is for internal inference validation, Russian/English smoke tests, and protocol verification. It is not a production default, public-distribution payload, installer payload, automatic-download target, recommendation for every machine, quality baseline, or performance baseline. UP05-WP01 remains responsible for LocalComet chat reliability; WP00 does not declare that work complete.
