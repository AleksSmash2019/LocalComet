# UP05-WP02 — Runtime archive envelope

## Approved runtime identity

The `llama-cpp-windows-x86-64-cpu-bootstrap` contract remains pinned to llama.cpp
`b10068`, `llama-b10068-bin-win-cpu-x64.zip`, `18,007,324` bytes, and SHA-256
`01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`.
The URL and redirect-host allowlist are unchanged.

## Exact archive envelope

The source-controlled catalog contains all 51 normalized top-level regular ZIP
members, each with an explicit disposition.  It has no default or pattern
disposition.  Unknown, missing, duplicate, unsafe, directory, symlink, or
case-colliding members fail before extraction.

`Install` contains exactly 30 files: `llama-server.exe` plus the 29 pinned DLLs
already hash-bound in `required_files`:

- `ggml-base.dll`, `ggml-cpu-alderlake.dll`, `ggml-cpu-cannonlake.dll`,
  `ggml-cpu-cascadelake.dll`, `ggml-cpu-cooperlake.dll`,
  `ggml-cpu-haswell.dll`, `ggml-cpu-icelake.dll`, `ggml-cpu-ivybridge.dll`,
  `ggml-cpu-piledriver.dll`, `ggml-cpu-sandybridge.dll`,
  `ggml-cpu-sapphirerapids.dll`, `ggml-cpu-skylakex.dll`,
  `ggml-cpu-sse42.dll`, `ggml-cpu-x64.dll`, `ggml-cpu-zen4.dll`,
  `ggml-rpc.dll`, `ggml.dll`, `libomp140.x86_64.dll`,
  `llama-batched-bench-impl.dll`, `llama-bench-impl.dll`,
  `llama-cli-impl.dll`, `llama-common.dll`, `llama-completion-impl.dll`,
  `llama-fit-params-impl.dll`, `llama-perplexity-impl.dll`,
  `llama-quantize-impl.dll`, `llama-server-impl.dll`, `llama-server.exe`,
  `llama.dll`, and `mtmd.dll`.

`RecognizedNotInstalled` contains exactly 21 ZIP members.  They are validated
as part of the envelope but are never opened for extraction, written to staging,
promoted, hashed as installed files, or launched:

- `ggml-rpc-server.exe`, `llama-batched-bench.exe`, `llama-bench.exe`,
  `llama-cli.exe`, `llama-completion.exe`, `llama-fit-params.exe`,
  `llama-gemma3-cli.exe`, `llama-gguf-split.exe`, `llama-imatrix.exe`,
  `llama-llava-cli.exe`, `llama-minicpmv-cli.exe`, `llama-mtmd-cli.exe`,
  `llama-mtmd-debug.exe`, `llama-perplexity.exe`, `llama-quantize.exe`,
  `llama-qwen2vl-cli.exe`, `llama-results.exe`,
  `llama-template-analysis.exe`, `llama-tokenize.exe`, `llama-tts.exe`, and
  `llama.exe`.

## License injection and final inventory

`LICENSE-MIT.txt` is deliberately not a ZIP member.  After archive identity and
envelope validation, acquisition verifies the source-controlled
`third_party/llama.cpp/LICENSE-MIT.txt` asset at exactly 1,078 bytes and SHA-256
`94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`, then
writes it into staging.  The promoted runtime therefore contains the 30
`Install` files plus this one license file, with no other member.

Post-install validation includes the injected license.  The launcher remains
bound to the installed `llama-server.exe` only.

## Bounded diagnostics and validation

Archive-envelope failures retain the existing structured diagnostic event and
may include a normalized member name, explicit disposition, and expected versus
observed member counts.  They never include redirect query strings, response
bodies, or frontend-provided authority.

The focused synthetic ZIP tests cover successful 51-member selection, skipped
executables, unknown executable/DLL/text members, missing installable and
recognized members, duplicate/traversal/directory rejection, disposition drift,
license identity failure, atomic promotion boundaries, and the bounded event
fields.  The separately ignored offline test accepts an explicit verified
archive path and validates the real b10068 archive only into a temporary test
directory.
