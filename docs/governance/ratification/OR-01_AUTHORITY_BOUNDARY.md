# OR-01 authority boundary

OR-01 authorizes one bounded Windows delivery increment. It is not authority to redesign LocalComet or to implement the broader UP00 blueprint.

## Authorized

- Record the owner decisions in repository governance documents.
- Configure the pinned Tauri 2 toolchain for a per-user Windows NSIS installer.
- Package the existing Python sidecar and a private runtime so installed launch does not depend on developer tools.
- Adapt the existing Rust sidecar supervisor for bounded startup readiness, failure cleanup, and shutdown.
- Add application-level single-instance protection using the existing Windows system boundary.
- Suppress terminal windows for the release application and its managed child.
- Use existing LocalComet metadata and icon assets.
- Create and validate Start Menu and desktop shortcuts and uninstall registration.
- Add packaging, lifecycle, installation, uninstall, negative-authority, and rollback tests directly required by UP00-WP01.
- Produce unsigned internal artifacts and human-review evidence.

## Not authorized

- New or changed frontend-to-Rust commands, events, capabilities, or raw IPC.
- Changes to the IPC schema, protocol version, semantic methods, or error contract.
- Changes to Python business logic, model management, Review Center, Prompt Studio, autonomous tasks, publication, or approval policy.
- Database, storage, schema, migration, ownership, retention, or data-lifecycle changes.
- Vault access or modification.
- New telemetry, analytics, crash upload, update check, model download, remote configuration, or launch-time network access.
- Generic process execution, a shell plugin, shell-string execution, or caller-supplied executable paths/arguments.
- Architecture decomposition, layer reorganization, Tauri major upgrade, broad dependency upgrade, signing infrastructure, automatic updates, or public-release claims.
- Any source work for UP01-UP10.

## Existing authority retained

- Rust continues to own process lifecycle, native-window lifecycle, capability enforcement, and outer IPC validation.
- Python continues to own LocalComet semantics behind the existing fixed framed-pipe protocol.
- Svelte remains an untrusted UI client and receives no new privileged authority.
- Existing user data remains owned by its current authority; installer files and runtime logs are kept separate from it.
- Existing typed commands and event channels remain unchanged.

## Stop rule

Stop before implementation if a safe installer requires an IPC redesign, data-lifecycle decision, architectural decomposition, new launch-time network dependency, user-data deletion, Vault access, broad toolchain upgrade, or any authority not explicitly listed as authorized.
