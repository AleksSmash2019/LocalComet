# Effort/thinking research notes — 2026-08-20

## Sources

1. Qwen official llama.cpp guide: https://qwen.readthedocs.io/en/stable/run_locally/llama.cpp.html
   The guide says llama.cpp supports Qwen3 from b5092. It documents `llama-server --reasoning-format deepseek` for extracting model thinking into `message.reasoning_content`, and explains that Qwen thinking/non-thinking has a soft switch while a hard chat-template switch is not exposed by llama.cpp in that guide. It suggests a custom chat template for always disabling thinking.

2. llama.cpp official server README: https://github.com/ggml-org/llama.cpp/blob/master/examples/server/README.md
   The current README documents `--reasoning-format {deepseek,none}` and says `deepseek` returns thinking separately under `message.reasoning_content`, while `none` leaves thinking inline in `message.content`. It also documents `--jinja`, which is required for tool use and reasoning format handling.

3. llama.cpp discussion #21445: https://github.com/ggml-org/llama.cpp/discussions/21445
   The discussion records per-request `thinking_budget_tokens` support when no command-line reasoning budget overrides it. The referenced implementation reads `thinking_budget_tokens` from the request body and maps it to reasoning budget tokens.

4. llama.cpp discussion #20408: https://github.com/ggml-org/llama.cpp/discussions/20408
   The discussion notes that generic `reasoning_effort` may be ignored by llama-server and discusses mapping effort tiers to thinking budgets as a workaround. It gives an example mapping discussed by participants: minimal 128, low 512, medium 2048, high 8192, xhigh 32768, max unlimited. This is research context, not an accepted LocalComet contract.

## Implementation implication

LocalComet should not silently claim that every model supports thinking. The safest contract is an explicit effort enum with `off`, `low`, `medium`, `high`, a bounded per-request reasoning budget, a capability/fallback status, and a separate `reasoning` stream channel. For Qwen3-family models served with Jinja/reasoning-format support, the gateway can request a budget using `thinking_budget_tokens`; for models without reasoning tags, effort must degrade honestly to standard content generation and the UI must say so. Existing security/request identity fields must include effort/budget in the canonical Rust digest so the sidecar cannot receive an unauthorised turn variant.
