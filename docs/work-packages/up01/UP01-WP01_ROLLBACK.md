# UP01-WP01 Rollback

## Rollback boundary

UP01 changes frontend navigation, a frontend-only Settings drawer, a versioned UI preference record, Diagnostics layout styles, tests, and work-package documentation. It does not change backend, IPC, Rust commands, databases, Vault content, model runtime, installer architecture, installation scope, or user chat content.

## Source rollback

Preferred rollback options:

1. Revert the UP01 commits in reverse order on `feat/up01-wp01-minimal-navigation-settings`.
2. If the branch has not been shared, abandon it and restore the predecessor branch at exact commit `821d49c2130bfacb8dcb5ccd5371bd0a24105497`.

Do not rewrite or reset `main`. Do not alter the UP00 predecessor commit.

## Preference rollback

The only new persistent record is `localcomet.ui.preferences.v1` with theme, locale, and Diagnostics visibility. The UP00 frontend does not read that key, so source rollback is safe without deleting it. The pre-existing `localcomet.ui.language` value is read only as a compatibility fallback and is not broadened.

No prompt, chat, model, credential, path, machine, Vault, database, or backend data requires rollback.

## Installer rollback

UP01 does not change installer architecture or scope. If installed-smoke validation fails because of UP01:

- stop publication and return the required blocker;
- retain the evidence and installer checksum;
- reinstall the previously accepted UP00 internal build only when a bounded human rollback is required;
- do not select any uninstall option that removes application data;
- verify shortcuts and processes belong to the intended installation before any uninstall action.

## Rehearsal acceptance

A disposable clone/worktree rollback rehearsal must show that reverting the UP01 commit range restores the exact UP00 source tree, aside from ignored build output, and that no backend, IPC, Vault, or data migration step is needed.
