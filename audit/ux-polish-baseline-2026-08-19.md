# LocalComet UX polish baseline — 2026-08-19

## Scope and guardrails

The goal is to improve clarity and visual polish without changing backend behavior, permissions, model contracts, navigation actions, or existing controls. No files are deleted, no npm dependencies are added, no commits or branches are created, and the Obsidian Vault is not touched. Every UI patch must be followed by frontend checks/tests and a hidden CDP smoke pass; the final state must retain 69/69 gates.

## Current visual baseline

The hidden CDP screenshot `localcomet_cdp_9223.png` was captured from the live chat route at 1800×1125. The layout is already coherent: dark glass surface, green accent, stable left navigation, compact model chip, readable user/assistant bubbles, and a low-profile composer. The strongest remaining visual opportunity is not structural replacement: it is improving information hierarchy and first-run guidance while preserving the current spacing, rounded surfaces, and navigation locations.

## Confirmed UX opportunities

1. The sidebar labels are technically accurate but the distinction between “Модели HF” and “Подобрать модель” is not self-explanatory to a novice. Copy should be clarified without removing or renaming the existing actions in a way that breaks tests or deep links.
2. The first-run onboarding correctly exposes live subsystem states, but its subtitle and environment terminology are aimed at technical users. Explanatory microcopy should make the next action obvious while keeping every diagnostic state honest.
3. The model chip and composer expose the correct controls, but the user receives little contextual help about what happens during `Validating`, `Loading`, or an unavailable-model state. Improvements should be presentational or localized and must not fake backend readiness.
4. The active chat screenshot contains substantial empty space when the conversation is short. This is acceptable for a focused desktop workspace; any visual change should avoid introducing disruptive animations or moving the composer away from its stable bottom position.
5. Existing accessibility contracts are strong: navigation buttons have labels/titles, the composer has a real label, and the HF search input has a localized `aria-label`. New text must use i18n keys rather than hardcoded UI copy.

## Non-goals

The small model’s factual limitations are not a UI defect and will not be “fixed” by changing model behavior as part of this polish pass. Computer Use, skills, model loading, HF downloads, ModelFit calculations, and security/approval contracts are treated as protected functionality.

## Baseline acceptance

A polish change is accepted only when it preserves the current visible actions and routes, keeps live backend state truthful, passes `npm run check`, `npm test`, the affected Rust/Python checks, and the final full gate suite, and remains usable through hidden CDP interaction without visible window flicker.

## UX patch verification checkpoint

The live hidden screenshot after the first polish block shows the model chip with a truthful `Модель: готова` badge. The settings model panel keeps the four-step setup progress visible and now retains the primary runtime action in a translucent sticky footer while the long model details scroll. The footer does not remove or rename any action; it only keeps the existing Disconnect/Connect/Setup controls reachable. Runtime probe remained `Ready` after the relaunch and model connection.

The visual hierarchy remains consistent with the baseline: sidebar width, navigation order, composer location, settings tabs, and model cards are unchanged. The added status badge improves scanability and the sticky action area improves first-run recoverability without relying on fake state.

## End-to-end visual checkpoint

The refreshed hidden chat screenshot shows the intended ordinary-user path clearly: a truthful `Модель: готова` badge in the header, a ready-state card with a plain-language local-only explanation, four concrete prompt cards, a stable composer at the bottom, and no approval dialog. The added gradient/shadow on the empty state is subtle and does not compete with the prompt cards. The settings screenshot separately confirmed that the sticky model action footer remains visible while the setup cards scroll.

The current end-to-end hidden flow passed: Chat → send prompt → assistant response → Новый чат clears the transcript while runtime remains Ready; HF search returns Qwen2.5 results and aria-label; ModelFit scan reaches hardware data and light-chat recommendation; Computer Use controls show no approval-card regression. These are verification findings, not simulated states.
