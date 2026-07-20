# UP00-WP01 rollback

Rollback removes only this branch's code/configuration/documentation delta. It never deletes LocalComet user data, logs, projects, knowledge files, or Vault content.

## Preconditions

1. Stop the installed LocalComet window normally and verify no managed child remains.
2. Record the installer, installed executable, branch HEAD, commit list, and worktree status.
3. If an installed build is present, run its registered uninstaller without opting into app-data deletion.
4. Verify installer-owned files and shortcuts are gone while `%LOCALAPPDATA%\LocalComet` user-owned state remains.

## Source rollback

For rehearsal, use a disposable clone made from the local repository beneath the ignored build root. Do not rehearse by mutating `main` or the primary feature worktree.

In the disposable clone:

1. Check out the final feature commit detached.
2. Record `git diff --name-status main...HEAD` and exact commit order.
3. Revert the UP00-WP01 commits newest-first using normal inverse commits or `git revert --no-commit`; do not use `git reset --hard` or broad checkout restoration.
4. Confirm the resulting tracked tree equals baseline `6c784ace543e345bdb8bd2f778be974dc89f2df5` byte-for-byte.
5. Run baseline-safe integrity and syntax checks.
6. Restore the final feature state in the disposable clone from the locally known commit and rerun integrity checks.

The primary feature worktree remains untouched throughout rehearsal.

## Runtime/artifact rollback

- Generated build workspaces and unsigned installers are non-authoritative artifacts; stop using the superseded installer and retain checksums/evidence for audit.
- Do not remove `%LOCALAPPDATA%\LocalComet`, because it is the established user-data/log root.
- Do not run an installer option that deletes application data.
- Do not alter the Vault or any project/document path.
- Reinstallation of a prior binary is allowed only after its exact identity and data compatibility are independently verified; this work package does not claim a public downgrade path.

## Rollback pass condition

Rollback passes only when the disposable source tree returns to the exact baseline, user-owned state is unchanged, installer-owned files are removable, the successful feature state can be restored, and the original repository remains on the clean feature branch.
