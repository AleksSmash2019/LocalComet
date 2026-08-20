# Open-source quality patterns for LocalComet — 2026-08-21

## Sources reviewed

| Project | Applicable pattern | LocalComet adaptation |
|---|---|---|
| llama.cpp server | Separate liveness/readiness endpoints from actual chat-completion behavior; expose inference options such as `--gpu-layers auto`, `--fit`, context size and performance timings. | Keep existing health/readiness checks separate from a real short completion/continuation/new-chat smoke. Preserve LocalComet's verified profile authority; do not silently override a chosen compute profile. |
| Ollama integration tests | Separate default unit tests from explicitly scoped `fast`, `release`, and broad-library integration suites. Start an isolated server where possible; support an explicit existing-server target; retain server logs for each harness-owned run. | Add a LocalComet hidden quality suite with fast synthetic assertions plus isolated runtime smoke. Do not test against a user-owned running runtime unless that mode is explicit and non-destructive. |
| Open Interpreter | Keep model harness and computer-use testing as explicit, provider-neutral subsystems rather than embedding unsafe ad-hoc shell flows in a chat path. | Extend synthetic Computer Use fixture tests and UI component rendering assertions; retain LocalComet approval, workspace and secret boundaries instead of adopting unrestricted execution. |

## Decision

The test system will use three tiers: **fast deterministic unit/component tests**, **synthetic UI/Computer Use contract tests**, and an **isolated model runtime smoke**. The suite will assert failure states as well as success states. It will not add dependencies, execute a user's desktop actions, or use a live external provider.

## References

[1]: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
[2]: https://github.com/ollama/ollama/blob/main/integration/README.md
[3]: https://github.com/openinterpreter/openinterpreter
