# UP05-WP01 Rollback

Status: source and installed rollback rehearsals passed.

## Source rollback

UP05-WP01 depends on the exact UP05-WP00 commit `fa664b16c48c0377841dc334b89b2b3868a0249c`. Revert only the R2 commits in reverse order. Do not reset, rewrite, or move `main`, the WP00 branch, or the prior blocked WP01 branch.

The completed rehearsal used external Git-object materializations, not a clone. It materialized the exact 359-file WP00 tree and a separate WP00 candidate, applied the bounded R2 patch forward, proved that candidate byte-identical to the exact 366-file implementation HEAD, and passed a reverse-apply check back to WP00. The canonical checkout was not mutated and no file was deleted. The approved catalog/trust proofs remained present and no GGUF or managed llama.cpp runtime payload was tracked.

Source result: PASS at `C:\Users\DNS\Documents\LocalComet-UP05-WP01-R2-Rollback-20260720T175300Z`; patch SHA-256 `87c93046ecbdd862538ae727eb5a8e1dc23d6f9113422e9ff655ef28a6eb5e88`.

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

Completed result: PASS. The registered uninstaller exited 0; the installation root, Start Menu/Desktop shortcuts, and uninstall registration were absent afterward. The approved model remained 1,117,320,736 bytes with SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, and the approved runtime executable remained 9,216 bytes with SHA-256 `3a8aea5f889c4b4c2ec41c98f4e1ed484bb7a40c4096883acb23d3cfe26b59fb`. Reinstall exited 0 and restored the final installed executable, shortcuts, and registration.

## Data and compatibility

Chat messages introduced by this package are bounded in-memory UI state and are not a persistence migration. The package adds no database schema, registry data format, cloud state, API key, or model-format migration. Rollback therefore requires no user-data transform.

## Unsafe rollback stop

Stop with `BLOCKED_UNSAFE_ROLLBACK` if exact process ownership, exact installer ownership, preservation of managed artifacts, or the WP00 target tree cannot be proven without broad or destructive action.
