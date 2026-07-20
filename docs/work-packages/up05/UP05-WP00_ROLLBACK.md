# UP05-WP00 Rollback

<!-- Rollback preserves unrelated user-owned artifacts and data. -->

## Source rollback

The branch is stacked directly on UP01-WP01 base 0467cf71e1cf0e0400d687c1829e7bd0de91eebc. Reviewable WP00 commits may be reverted in reverse order. A clean branch reset/recreation at the exact base restores the predecessor tree without touching main.

Rehearsal result: PASS. The complete feature patch and the catalog-only patch both passed reverse-apply checks against the exact base. `main` and `origin/main` remained unchanged.

## Managed artifact rollback

Rollback records exact PRE01/WP00-created relative destinations. Remove only the catalog-declared bootstrap model file and the exact bootstrap runtime package directory after revalidating their identities. Never scan or delete unrelated models/runtimes.

If a destination does not match the WP00 created-file manifest, stop rather than deleting it.

## Derived state

WP00 uses live derived installed status and creates no persistent trusted inventory. Ephemeral runtime-state credentials remain owned by the managed supervisor and are deleted on stop. A missing runtime-state directory requires no restoration.

A future optional cache must remain non-authoritative and must use a sibling temporary file, schema validation, flush and close, Windows-supported atomic replacement, reread, and exact post-write validation. Failure preserves the prior valid cache. Current WP00 state needs no cache rollback: deleting, corrupting, or inventing inventory content cannot approve anything, and live validation reconstructs state from catalog-declared bytes.

## Preservation

Rollback must preserve:

- unrelated models and runtimes;
- LocalComet settings and user data;
- repository work outside WP00;
- main and origin/main;
- the Obsidian Vault;
- external evidence and upstream pin records unless the owner explicitly removes them.

## Completed rehearsal

The bounded rehearsal passed:

- only the exact catalog-declared runtime ID `llama-cpp-windows-x86-64-cpu-bootstrap` and model ID `qwen2.5-1.5b-instruct-q4-k-m` destinations were selected;
- both destinations were moved aside using same-volume operations without deleting their bytes;
- the absence state was observed while unrelated managed content and user data remained present;
- both destinations were restored to their original catalog-declared locations;
- live installed state reconstructed without a persistent inventory;
- restored bytes, hashes, containment, compatibility, and launchability validated successfully;
- no owned runtime process remained;
- no model/runtime bytes entered Git or installer resources;
- the Obsidian Vault was neither read nor modified.

Rollback result: PASS. The successful feature state was restored cleanly.
