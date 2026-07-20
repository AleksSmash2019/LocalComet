# UP05-WP00 Approved Artifact Catalog Schema

<!-- Canonical schema documentation. -->

Catalog path:

desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json

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
- supported_api
- license
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
- license
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

## Safe projections

Frontend responses may include stable IDs, display/version/platform/architecture/format/quantization, artifact filename, expected bytes/SHA-256, license, status, compatibility IDs, validation status, verified time, and catalog identity/digest.

They never include resolved absolute paths, URLs, executable arguments, environment, credentials, or approval mutation controls.
