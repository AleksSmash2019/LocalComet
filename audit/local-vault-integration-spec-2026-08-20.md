# LocalComet local-folder Vault integration specification

## Scope

The integration is limited to the local folder `C:\Users\DNS\Documents\LocalCometVault`. It must not use the Obsidian application, Local REST API, MCP, browser sessions, cloud sync APIs, or any path outside the configured Vault root.

The adapter is a filesystem capability for Markdown notes, not an Obsidian plugin. It may read, propose, create, and update `.md` files inside the Vault after the workspace root has been validated.

## Safety boundary

The Vault root is canonicalized once and stored as an identity. Every requested relative path is normalized beneath that root. Absolute paths, drive-qualified paths, `..` traversal, symlinked files, symlinked directories, junction escapes, and paths inside `.obsidian` are rejected. Non-Markdown files are not writable through the adapter. The adapter does not delete files.

All reads are bounded by a per-file byte limit. Writes use UTF-8, an atomic temporary file in the destination directory, and replace semantics. An update must carry the expected SHA-256 of the current file; a mismatch returns a conflict instead of overwriting a newer note. New note creation must fail if the target already exists.

## Write workflow

The default workflow is read-only inventory and preview. A proposed change contains the canonical relative path, current SHA-256, new body SHA-256, and a unified diff. Applying a proposal is a separate operation. This preserves the project memory rule: verified change -> proposed diff -> approval -> Vault update.

No Vault content will be changed merely by connecting or scanning the root. The first implementation and tests use temporary directories only; the real Vault is inspected read-only.

## Initial operations

The initial adapter surface is deliberately small: `list_markdown`, `read_markdown`, `propose_create`, `propose_update`, and `apply_proposal`. No delete, rename, recursive arbitrary write, or binary operation is included.

## Acceptance criteria

The adapter must pass tests for canonical root validation, ordinary read/create/update, optimistic-concurrency conflicts, absolute/traversal paths, symlink escapes, `.obsidian` exclusion, non-Markdown rejection, byte limits, atomic write behavior, and no-delete behavior. The LocalComet gates must remain green after integration changes.
