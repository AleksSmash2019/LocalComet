# UP05-WP02 packaged profile isolation fix

## Root cause

The packaged startup log resolved %LOCALAPPDATA%\LocalComet directly, while
the backend passed Tauri's Windows known-folder local_data_dir() into the
managed artifact service. Changing the child process environment therefore
split frontend startup logging from backend model/runtime storage.

## Path map

| Consumer | Before | After |
| --- | --- | --- |
| Startup log | %LOCALAPPDATA%\LocalComet\logs | authoritative application-data root + logs |
| Approved model final path | Tauri local-data directory + LocalComet\models | authoritative root + models |
| Acquisition partial/staging | Tauri local-data directory + LocalComet\acquisition | authoritative root + acquisition |
| Installed-model discovery/removal | managed artifact roots from Tauri local-data directory | managed artifact roots from authoritative root |
| Runtime/model arguments and key state | managed artifact roots from Tauri local-data directory | managed artifact roots from authoritative root |

## Contract

LOCALCOMET_APP_DATA_ROOT is an opt-in exact LocalComet application-data
directory. It must be a nonempty absolute local filesystem path; empty,
relative, and Windows UNC paths are rejected. Invalid values stop startup
without falling back to the normal profile.

Without the override, the production root is unchanged:

app.path().local_data_dir()/LocalComet

The backend owns every model-related path. The frontend supplies no destination,
URL, hash, model, or staging path.

## Regression coverage

- default production path remains unchanged;
- absolute overrides select the exact root and startup logging uses it;
- empty, relative, and network-share overrides are rejected;
- runtime, model, state, and acquisition paths derive from one root;
- a synthetic model in a separate default profile is neither discovered nor
  selected as the managed-model removal destination;
- runtime --model and --api-key-file arguments use paths under that root.

## Packaged smoke result

The rebuilt NSIS package was launched with a fresh
LOCALCOMET_APP_DATA_ROOT. Startup logs and acquisition staging appeared only
under that root. No model/runtime directories were created, the UI remained in
the no-model setup state, and no LocalComet process remained after closing the
window. No model download or chat action was performed.
