# UP05-WP00 Rollback

<!-- Rollback preserves unrelated user-owned artifacts and data. -->

## Source rollback

The branch is stacked directly on UP01-WP01 base 0467cf71e1cf0e0400d687c1829e7bd0de91eebc. Reviewable WP00 commits may be reverted in reverse order. A clean branch reset/recreation at the exact base restores the predecessor tree without touching main.

## Managed artifact rollback

Rollback records exact PRE01/WP00-created relative destinations. Remove only the catalog-declared bootstrap model file and the exact bootstrap runtime package directory after revalidating their identities. Never scan or delete unrelated models/runtimes.

If a destination does not match the WP00 created-file manifest, stop rather than deleting it.

## Derived state

WP00 uses live derived installed status and creates no persistent trusted inventory. Ephemeral runtime-state credentials remain owned by the managed supervisor and are deleted on stop. A missing runtime-state directory requires no restoration.

## Preservation

Rollback must preserve:

- unrelated models and runtimes;
- LocalComet settings and user data;
- repository work outside WP00;
- main and origin/main;
- the Obsidian Vault;
- external evidence and upstream pin records unless the owner explicitly removes them.

## Rehearsal

Perform an isolated simulation using copied manifests and empty placeholder paths, then prove:

- only exact WP00 relative paths are selected;
- base tree restoration is clean;
- unknown/colliding files stop rollback;
- successful provisioned state can be restored from the same already-downloaded verified staging bytes during the mission;
- no model/runtime bytes enter Git or installer resources.
