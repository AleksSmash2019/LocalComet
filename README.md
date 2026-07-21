# LocalComet

LocalComet is a private, local-first Windows AI assistant. It securely installs
a verified llama.cpp runtime and Qwen GGUF model, then runs chat entirely on the
user's computer without requiring Ollama, LM Studio, cloud inference, or an
OpenAI API key at runtime.

## Features

- Local AI chat on Windows
- Built-in llama.cpp runtime management
- Approved model and runtime catalog
- Exact URL and redirect-host validation
- File-size and SHA-256 verification
- Secure ZIP archive-envelope validation
- Atomic installation and cancellation cleanup
- Model removal and verified redownload
- Isolated application-data profiles
- Installer continuity and rollback validation

## How Codex was used

Codex was the primary coding agent used to build and validate LocalComet.

Codex helped with:

- Rust and Tauri backend implementation
- Svelte and TypeScript interface development
- Secure model and runtime acquisition
- SHA-256, size, URL, and redirect validation
- Atomic installation and cancellation cleanup
- Runtime archive-envelope security
- Automated Rust and frontend tests
- Windows NSIS packaging
- Packaged application debugging
- Uninstall and reinstall continuity testing
- Installer rollback rehearsal
- Git checkpoints and evidence collection

Development was split into small bounded missions. Each mission had a precise
scope, Git preflight, security boundaries, verification commands, evidence
requirements, and an exact PASS or BLOCKED stop condition.

## How GPT-5.6 was used

GPT-5.6 with high reasoning was used as an architecture and engineering
gatekeeper.

It helped with:

- Reviewing Codex results and evidence
- Separating proven facts from assumptions
- Classifying technical blockers accurately
- Protecting project scope and Git state
- Designing the shortest safe next engineering task
- Reviewing security boundaries
- Planning operator-assisted packaged acceptance
- Tracking completed and pending quality gates

GPT-5.6 did not replace product testing. Its recommendations were validated
through source tests, offline package gates, real Windows installer runs, local
chat acceptance, and rollback rehearsal.

## OpenAI Build Week 2026 contribution

During OpenAI Build Week, LocalComet received a major production-focused
expansion:

- Approved model and runtime acquisition
- Verified and atomic artifact installation
- Exact redirect-host allowlists
- Packaged application-data isolation
- Built-in llama.cpp runtime management
- Runtime archive-envelope validation
- Secure license provenance handling
- Local model connection and chat acceptance
- Model removal and verified redownload
- Windows uninstall and reinstall continuity
- Approved installer rollback and restoration

## Technology

- Rust
- Tauri 2
- Svelte
- TypeScript
- Vite
- llama.cpp
- GGUF
- Qwen2.5-1.5B-Instruct
- Cargo
- Vitest
- NSIS
- Windows

## Installation

1. Open the Build Week release:
   https://github.com/AleksSmash2019/LocalComet/releases/tag/v0.0.0-build-week-2026
2. Download `LocalComet_0.0.0_x64-setup.exe`.
3. Run the installer.
4. Open LocalComet.
5. Open **Settings → Models**.
6. Install the approved runtime and model.
7. Press **Connect**.
8. Start a local chat.

The first setup downloads approximately 1.1 GB.

## Verified Build Week candidate

- Platform: Windows x64
- Installer size: `13,878,331` bytes
- Installer SHA-256:
  `d17f84d0cbcb9a0503cc1c1196c80a126bc61565c04170c644b50530fd4c48eb`
- Phase A checkpoint:
  `a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`

The accepted candidate passed Rust tests, frontend tests, offline Cargo and
Clippy gates, NSIS packaging, real local inference, cancellation cleanup,
model removal and redownload, uninstall/reinstall continuity, and rollback
rehearsal.

## Privacy

Local inference runs through a bundled llama.cpp runtime on the loopback
interface. The accepted local chat path did not use remote inference.

## License

See the repository license and included third-party attribution files.