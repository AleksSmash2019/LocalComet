# LocalComet UX/UI improvement pass — verified result

**Date:** 2026-08-21  
**Scope:** first-run onboarding, managed model setup, chat composer, reasoning effort, visual hierarchy, accessibility and launch verification.  
**Test mode:** hidden checks only; no synthetic data was added to the product surface and no user files, models, messages or browser state were changed.

## Delivered improvements

| Surface | Verified change | Reasoning |
|---|---|---|
| Global visual system | The desktop surface now favors the native Windows UI font stack, a wider readable transcript column, tightened default rhythm, and a reduced-motion fallback. | Reduces generic web-app styling and improves legibility without a dependency or asset change. |
| Onboarding | Technical readiness remains truthful, but it now ends in one contextual primary action: choose/start a model until chat is ready, then open chat. | A beginner does not need to interpret six equally weighted infrastructure checks to know what to do next. |
| Managed model drawer | The hero uses compact readiness cues; the launch action names the actual selected model; automatic engine/compute selection is stated clearly; cards and decorative mass are reduced. | Model, engine and compute mode are distinct concepts, so the UI explains the automatic safe path rather than asking a user to infer one. |
| Composer | Effort is visible as an explicit control with the current level; voice output has an accessible pressed state; unsupported speech recognition shows an inline status message instead of a blocking system alert. | Makes high-frequency controls self-explanatory and keeps interruptions in context. |
| Computer Use cards | The earlier reliability pass provides action, factual state, reason and next step rather than hiding the outcome behind screenshot preview/details. | The user can distinguish completion, approval, block and replan without guessing. |

## Product rationale

The selected interaction model is a guided local cockpit: **current readiness → one recommended next action → optional alternatives**. It adopts the low-cognitive-load model-management direction used by desktop local-AI products while preserving LocalComet's verified local runtime and approval boundaries. Jan, for example, shows hardware-fit signals and a recommended model option before download; Ollama positions download and chat as an intentionally direct path.[1][2]

## Verification

| Gate | Result |
|---|---|
| `npm run check` | PASS — 0 errors, 0 warnings |
| `npm test -- --run` | PASS — 26 files, 404 tests |
| Tauri debug build | PASS |
| Updated LocalComet launch | PASS — responsive process, `LC_START_200` |

## Retained boundaries

The UI does not claim a runtime, model, compute mode, GPU offload or model capability that the existing stores have not verified. Advanced engine/compute controls remain an explicit follow-up rather than a fabricated readiness signal. Computer Use approval and safety boundaries are unchanged.

## References

[1]: https://www.jan.ai/docs/desktop/manage-models
[2]: https://ollama.com/blog/new-app
