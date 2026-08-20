# LocalComet UX/UI baseline — 2026-08-20

## Scope

Hidden code-and-state review of the daily chat surface, onboarding, model setup, sidebar, composer, effort selector and Computer Use result cards. No user UI interaction was executed during this review.

## Confirmed friction points

| Area | Current friction | UX direction |
|---|---|---|
| First run | The environment checklist is accurate but does not prioritize the one action that brings the user to a working chat. | Turn it into a progressive readiness path with a clear recommended model, visible engine mode, and one primary next action. |
| Model and compute setup | A model filename, engine/runtime and compute profile are technically separate concepts. They can appear as a dense setup form without a plain-language summary. | Keep `Auto — recommended` as the default; show the actual selected compute mode and engine with an explanation and reserve detailed overrides for disclosure. |
| Composer | The input is functional, but the effort control is visually too small and unsupported state relies primarily on opacity. | Make effort readable as a compact labelled control and state why it is unavailable, without adding a modal. |
| Chat header | The selected model badge shows raw technical identity and connection state together in a tight chip. | Make the connection signal scanable and keep technical details as secondary information. |
| Conversation navigation | Core navigation works but chat grouping gives little affordance for the current conversation and collapse/mobile state. | Strengthen selected state and simplify low-frequency navigation hierarchy. |
| Computer Use | Result cards have been improved, but setup/help language should continue to distinguish completed, blocked, approval-needed and replan states. | Use factual status labels rather than generic success/error decoration. |

## External product cues retained

Jan presents hardware fit before download, marks a recommended size/quantization, and provides visible download progress/cancellation.[1] Ollama presents model download and chat as a compact path.[2] LocalComet should retain stronger safety and local verification, while adopting this lower cognitive load.

## References

[1]: https://www.jan.ai/docs/desktop/manage-models
[2]: https://ollama.com/blog/new-app

## Chosen implementation direction

The UI will use a **guided-local cockpit** pattern rather than a dashboard full of equal-weight controls. The primary visual rhythm is: current readiness, one recommended next action, then optional alternatives. Emerald remains the signal colour for a verified local path; amber and red are reserved for genuine waiting and error states. No generated visual assets are required because the task is an editable, functional desktop interface rather than a UI image deliverable.

The immediate work is limited to the most visible paths: a progressively explained onboarding screen, a compact model drawer with one primary launch action and quiet secondary routes, a clearer effort control inside the composer, reduced visual noise in app-wide chrome, and localized user-facing state labels. Model, runtime and compute truth continue to come only from existing stores; unavailable facts remain unavailable rather than being inferred in the UI.
