# UP05-WP02 — Download State Machine

Each job is keyed by an opaque application-generated job ID and a catalog
artifact ID. Only one active job may exist for an artifact.

```text
awaiting_confirmation → checking_disk → downloading
                                        ↓
       cancelling ←────────────────────┘
           ↓
       cancelled

downloading → verifying_size → verifying_hash → validating_artifact
 → installing → completed
             └────────────────────────────────────────────→ failed
```

`cancelled`, `completed`, and `failed` are terminal. A state records expected
and received byte counts, calculation-safe percent, UTC millisecond timestamps,
and a bounded safe error code. A duplicate start returns the existing active
job rather than creating a second transfer.

Temporary bytes live only below `%LOCALAPPDATA%/LocalComet/acquisition`, named
from the opaque job ID and ending in `.partial`. Partial bytes are verified
before an atomic rename and are never an installed artifact. At startup, only
owned stale partial files are removed; they are never promoted.
