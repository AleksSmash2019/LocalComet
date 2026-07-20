# UP02-WP01 Rollback

## Source rollback

The exact predecessor is `ee221944eca092580e333b804f4e408a89a0bc76` on `feat/up05-wp01-r2-real-model-chat`. A bounded rehearsal uses a temporary detached worktree or equivalent read-only tree comparison so the active feature branch and user data are not destructively reset.

Verification criteria:

- the predecessor tree matches the required commit exactly;
- removing the UP02 commits removes the trusted context, new chat guidance, Settings capability summary, and UP02 tests/docs;
- predecessor chat, runtime, HF1 layout, and installer source remain recoverable;
- reconstructing the feature from its ordered commits produces the feature tree again;
- managed runtime/model data, UI preferences, chat data, Vault, and user-owned files are not deleted or changed.

## Installed rollback

Use the existing per-user uninstaller. Confirm it removes only application-owned installed files and shortcuts while preserving external managed runtime/model and user-owned data. Reinstall the predecessor only from an already approved local artifact if available; do not download anything.

## Unsafe conditions

Stop with `BLOCKED_UNSAFE_ROLLBACK` if exact targets cannot be proven, if rollback would require deleting user-owned data, or if the successful feature state cannot be reconstructed cleanly.
