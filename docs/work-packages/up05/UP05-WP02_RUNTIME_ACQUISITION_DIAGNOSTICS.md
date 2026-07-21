# UP05-WP02 runtime acquisition diagnostics checkpoint

## Scope

Phase A records a bounded, backend-owned terminal failure event before removing
the owned acquisition partial or runtime staging directory.  It does not alter
the approved artifact catalog, source URLs, hashes, archive contract, or
frontend acquisition authority.

The event is appended and flushed to:

`<LOCALCOMET_APP_DATA_ROOT>/logs/acquisition-events.jsonl`

Each JSONL record contains only `schema_version`, `timestamp_utc_ms`, artifact
kind and immutable catalog ID, terminal status, bounded stage, existing bounded
error code, received and expected byte counts, cleanup completion, and final
artifact existence.  It contains no URL, query string, path, response body,
credential, or frontend-supplied diagnostic content.

## Runtime failure path

| Bounded stage | Existing backend error codes | Cleanup / published state |
| --- | --- | --- |
| `transfer` | `download_failed`, redirect/content-type/partial I/O and preflight failures | owned partial and staging are removed; job is `failed` with the original code |
| `size_verification` | `size_mismatch` | owned partial and staging are removed; job is `failed` |
| `hash_verification` | `hash_mismatch`, `hash_read_failed` | owned partial and staging are removed; job is `failed` |
| `archive_validation` | `invalid_runtime_archive`, `unexpected_runtime_member`, `runtime_member_hash_mismatch`, `missing_runtime_member` | owned partial and staging are removed; job is `failed` |
| `staging_extraction` | `staging_create_failed`, `staging_write_failed` | owned partial and staging are removed; job is `failed` |
| `atomic_promotion` | `atomic_install_failed` | owned partial and staging are removed; job is `failed` |
| `post_install_validation` | `post_install_validation_failed` | invalid installed output is removed, then owned temporary resources are removed; job is `failed` |

Cancellation remains a non-failure terminal state and produces no failure
event.  A diagnostic write failure is ignored so the original acquisition
error remains authoritative.  A successful acquisition produces no terminal
failure event.

## Focused coverage

Synthetic-fixture tests cover the stage mapping, distinct size/hash/archive/
staging/promotion/post-install outcomes, event persistence before cleanup,
partial and staging cleanup, no final artifact after failure, no event on
success, catalog-owned identity and backend-owned values, sensitive-query
exclusion, and app-data-root isolation.
