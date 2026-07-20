# UP05-WP00 Approved Artifact Catalog Schema

<!-- Canonical schema documentation. -->

Catalog path:

desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json

Published identity:

- schema version: 1
- catalog ID: `localcomet-approved-artifacts`
- catalog version: `1.0.0`
- exact catalog-byte SHA-256: `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`

## Top-level schema

- schema_version: integer, exactly 1
- catalog_id: exactly localcomet-approved-artifacts
- catalog_version: bounded non-empty version identifier
- runtimes: sorted by runtime_id
- models: sorted by model_id

Unknown keys and duplicate JSON keys are rejected.

## Runtime entry

Required fields:

- runtime_id
- provider
- release_tag
- platform
- architecture
- variant
- upstream_repository
- upstream_revision
- asset_filename
- asset_bytes
- asset_sha256
- archive_format
- managed_relative_path
- executable_relative_path
- required_files
- permitted_bind_scope
- supported_api_protocol
- license_id
- public_distribution
- status

required_files entries contain a safe package-relative path, positive byte count, and lowercase SHA-256. Paths are unique under Windows case folding and sorted. The executable must be present in required_files.

WP00 permits only Windows, x86-64, CPU, ZIP, loopback-only, OpenAI-compatible-v1, non-public approved entries.

## Model entry

Required fields:

- model_id
- provider
- family
- display_name
- format
- quantization
- upstream_repository
- upstream_revision
- asset_filename
- asset_bytes
- asset_sha256
- license_id
- compatible_runtime_ids
- managed_relative_path
- public_distribution
- installer_bundled
- bootstrap_purpose
- status

compatible_runtime_ids are unique, sorted, non-empty, and must reference runtime IDs in the same catalog. WP00 permits only GGUF, non-public, non-installer-bundled, explicitly approved internal bootstrap entries.

## IDs

IDs match a bounded lowercase ASCII grammar:

- first character: a-z or 0-9
- remaining characters: a-z, 0-9, period, underscore, or hyphen
- total length: 3 through 96 bytes

IDs do not contain paths and are never derived from private paths.

## Hashes and sizes

Every SHA-256 is exactly 64 lowercase hexadecimal characters. Artifact size and required-file sizes are positive unsigned integers. Model and archive artifact hashes are over exact raw upstream bytes.

The source catalog digest is SHA-256 over exact canonical catalog file bytes. It is evidence, not a semantic or self-referential hash field inside the catalog.

Approved runtime pin:

- ID: `llama-cpp-windows-x86-64-cpu-bootstrap`
- release/revision: `b10068` / `571d0d540df04f25298d0e159e520d9fc62ed121`
- asset/bytes: `llama-b10068-bin-win-cpu-x64.zip` / 18,007,324
- SHA-256/license: `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89` / MIT

Approved model pin:

- ID: `qwen2.5-1.5b-instruct-q4-k-m`
- repository/revision: `Qwen/Qwen2.5-1.5B-Instruct-GGUF` / `91cad51170dc346986eccefdc2dd33a9da36ead9`
- asset/bytes: `qwen2.5-1.5b-instruct-q4_k_m.gguf` / 1,117,320,736
- SHA-256/license: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` / Apache-2.0

## Paths and filenames

Catalog paths use relative forward-slash components only. Validation rejects:

- absolute and UNC paths;
- Windows drive-relative forms;
- backslashes;
- dot and dot-dot components;
- empty components;
- NUL;
- paths outside the required runtime/model prefix;
- case-fold collisions;
- executable paths outside the runtime package.

Asset filenames are basenames only. Duplicate artifact filenames mapped to conflicting managed locations are rejected.

## Installed state

WP00 creates no persistent installed inventory. Installed state is a live derived projection over catalog-declared managed paths, current byte counts, hashes, file format, containment, and compatibility. Therefore an AppData file cannot add approval, and missing, corrupt, stale-digest, traversal-bearing, or unknown-ID inventory content is inert.

Any future cache remains non-authoritative. It must be written through a sibling temporary file, schema-validated, flushed and closed, atomically replaced on Windows, reread, and exactly post-write validated. Every read must reconcile catalog ID/version/digest, known artifact IDs, relative containment, current bytes, and current SHA-256. Failure preserves the previous valid cache; deletion causes safe live reconstruction.

## Safe projections

Frontend responses may include stable IDs, display/version/platform/architecture/format/quantization, artifact filename, expected bytes/SHA-256, `license_id`, status, compatibility IDs, validation status, verified time, and catalog identity/digest.

They never include resolved absolute paths, URLs, executable arguments, environment, credentials, or approval mutation controls.
