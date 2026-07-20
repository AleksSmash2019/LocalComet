# UP05-WP01 Rollback

Status: bounded R2 rollback contract; rehearsal evidence pending.

## Source rollback

UP05-WP01 depends on the exact UP05-WP00 commit `fa664b16c48c0377841dc334b89b2b3868a0249c`. Revert only the R2 commits in reverse order. Do not reset, rewrite, or move `main`, the WP00 branch, or the prior blocked WP01 branch.

The rehearsal must occur in a clean external local clone. After reversing R2, verify that the resulting tracked tree equals the WP00 tree, the approved catalog and trust tests remain present, and no model/runtime bytes appear in Git. Do not perform a destructive reset in the canonical checkout.

## Runtime rollback

Before rollback, request bounded cancellation of any active inference, stop the managed runtime through its typed command, close LocalComet normally, and prove no LocalComet-owned `llama-server`, sidecar, or application process remains. If graceful cleanup reaches its bound, rely on the existing contained job/process ownership to terminate only the owned process tree and record the typed shutdown result.

UP05-WP01 does not change artifact approval or acquire new bytes. The approved model and llama.cpp installation under LocalComet-owned app data must remain unchanged and hash-valid across rollback.

## Installed application rollback

1. Resolve the current uninstaller only from the exact current-user LocalComet uninstall registration.
2. Verify the resolved executable remains under the expected per-user LocalComet installation directory.
3. Close the app and prove owned processes are stopped.
4. Run that exact uninstaller without selecting app-data removal.
5. Verify installer-owned executable, resources, shortcuts, and uninstall registration are removed.
6. Preserve LocalComet app data, including the approved managed runtime/model and their metadata.
7. If restoring a prior internal installer, validate its checksum and install it current-user; launch only through its Start Menu shortcut.

Never delete or recursively modify broad profile, app-data, repository, Vault, or legacy-checkout paths.

## Data and compatibility

Chat messages introduced by this package are bounded in-memory UI state and are not a persistence migration. The package adds no database schema, registry data format, cloud state, API key, or model-format migration. Rollback therefore requires no user-data transform.

## Unsafe rollback stop

Stop with `BLOCKED_UNSAFE_ROLLBACK` if exact process ownership, exact installer ownership, preservation of managed artifacts, or the WP00 target tree cannot be proven without broad or destructive action.
