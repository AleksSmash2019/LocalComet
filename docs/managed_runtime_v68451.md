# LocalComet v6.84.5.1 Managed llama.cpp Runtime

v6.84.5.1 introduces a managed runtime path for one engine only: `llama.cpp`.

Production runtime packages remain external to the repository under `%LOCALAPPDATA%\LocalComet\runtimes\llama.cpp`. A package is runnable only when its canonical `runtime_manifest.json` and `llama-server.exe` hash match LocalComet-controlled approval metadata. The source-controlled production registry intentionally contains zero approved entries in this release, so the truthful default UI state is `Managed Runtime: Not installed`.

Managed models are scanned only from `%LOCALAPPDATA%\LocalComet\models`, direct children only, `.gguf` only, with bounded count and size. The frontend receives opaque `model_id` values, sanitized display names, sizes, availability, and file-identity fingerprints, never absolute paths.

The runtime supervisor owns the private loopback port, per-launch credential file, bounded logs, readiness checks, and shutdown. The Python sidecar receives the credential only through the fixed internal `model.managed.attach` method and drops it through `model.managed.detach`. The Svelte UI cannot provide executable paths, model paths, ports, credentials, environment variables, or raw runtime arguments.

Tests use `tools/test_fixtures/fake_managed_llama_server.py`, launched only as a source-only Python fixture through test code. It is not a production engine, is not in the production registry, is not installed under managed runtime roots, and no `.exe`, `.bat`, or `.ps1` fixture is authored by this release.
