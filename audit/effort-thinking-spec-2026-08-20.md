# LocalComet effort/thinking design — 2026-08-20

## User-facing levels

| UI level | Wire value | Thinking budget | Intended behavior |
|---|---|---:|---|
| Выкл. | `off` | 0 | Disable model-native thinking when the provider/template honors the request; only normal content is shown |
| Низкий | `low` | 512 | Short reasoning budget for quick hard questions |
| Средний | `medium` | 2048 | Balanced reasoning budget; default for reasoning-capable models |
| Высокий | `high` | 8192 | Deep reasoning budget, bounded by the existing 4096 generation cap only for visible completion, not UI state |

## Safety and compatibility rules

1. The effort enum is validated in the frontend bridge, Rust command, Python turn validator, and gateway request payload.
2. Effort and the resulting budget are included in the canonical Rust model-turn digest so the authorized request cannot be changed after reservation.
3. The gateway sends `thinking_budget_tokens` only when the selected model is detected as reasoning-capable. Detection is conservative and based on the bound model identity/family: Qwen3/Qwen3.5 and known reasoning families; unknown/custom models fall back to normal content generation.
4. The frontend always keeps the selector available, but shows a truthful unsupported/fallback status when the selected model cannot expose a separate reasoning stream.
5. Reasoning is emitted on the existing `content`/`reasoning` stream-channel vocabulary. Reasoning never appends to assistant visible `body`; it is stored in a bounded `reasoning` field and rendered as a collapsed disclosure block.
6. Off remains the safe default for non-reasoning models. Medium is the default for reasoning-capable models only if the user explicitly selects it; otherwise the persisted preference defaults to off to avoid surprising latency.
7. Existing tool-call and terminal event ordering remains unchanged. Reasoning deltas may occur between `model.turn.started` and content/terminal events and count toward the same bounded output budget.
8. If a provider returns no separate `reasoning_content`, the UI remains usable and shows a concise "reasoning unavailable for this model" status rather than fabricating reasoning.

## Implementation order

Frontend preference/types -> authenticated Rust payload -> Python gateway validation/budget mapping -> provider SSE split -> frontend stores/message rendering -> localization/tests/live audit.
