# UP05-WP02 — Security Model

The approved artifact catalog is the authority for acquisition identity. It
supplies the exact HTTPS primary URL, redirect-host allowlist, filename, byte
count, SHA-256, archive/format details, and managed relative destination. The
frontend supplies only a validated catalog artifact ID, then only an opaque job
ID for polling or cancellation.

The downloader manually validates every HTTPS redirect before following it.
Certificate validation remains enabled. It sends no browser credentials,
cookies, tokens, or frontend-provided headers. The only permitted upstream
identities are the catalog-declared GitHub release and Hugging Face artifact
origins/CDNs.

Downloads stream to an owned temporary file. Exact size and SHA-256 are checked
before installation. GGUF bytes must have the `GGUF` magic. Runtime ZIP entries
must be listed catalog files with safe relative paths; traversal, absolute,
drive-relative, duplicate/case-colliding, symlink, and unexpected entries fail.
The verified staging directory or model file is atomically renamed into the
catalog-declared managed root and revalidated from disk.

The acquisition authority belongs only to the desktop downloader after an
explicit UI confirmation. The language model, chat request, JavaScript, and
AssistantContext retain no internet, generic filesystem, shell, Vault, or tool
authority.
