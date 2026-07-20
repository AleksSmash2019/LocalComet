# UP02-WP01-HF2 — UI hygiene and Project Knowledge truthfulness

## Objective

Remove production-visible fixtures, dead or misleading controls, ambiguous Settings semantics, redundant build detail, and raw chat telemetry while preserving the accepted local-model chat and minimal LocalComet visual language.

This hotfix is stacked on UP02-WP01 commit b33f0ad85ec4c9058ee10a86fe2936c187fa3c11.

## Bounded inventory

VISIBLE_CONTROL_INVENTORY.tsv records every interactive or control-like item in the primary rail, thread sidebar, chat toolbar, status area, transcript/composer, Project Knowledge row, model drawer, Settings, Diagnostics, and About. The inventory records labels, accessible names, icons, handlers, actions, state, keyboard behavior, functionality, duplication, fixtures, and disposition.

## Planned corrections

- Replace the custom brightness-like Settings path with a recognizable gear in the existing local Icon component.
- Preserve only brand, Chat, and bottom-aligned Settings in the primary rail.
- Hide the cancellation-demo thread from production without deleting its test fixture or any persisted chat.
- Remove redundant sidebar version/developer labels because version/build remain in Settings → About.
- Make the header sidebar toggle narrow-layout-only and localize it; localize Diagnostics.
- Hide disabled Tools and installer placeholder buttons and remove raw request metrics from normal chat.
- Remove no-op diagnostics tabs and production demo controls while preserving underlying test fixtures.
- Keep all real model setup, runtime, transcript, retry, Settings, and Diagnostics actions.

## Project Knowledge diagnosis

The typed preview, decision, and bounded injection pipeline exists and is tested. Production adapter construction, however, requires an externally configured LOCALCOMET_KNOWLEDGE_VAULT path and otherwise returns no adapter. The installed acceptance failure therefore reflects a partial pipeline with no current production source-selection/authority contract.

HF2 does not add Vault, repository, file, RAG, memory, indexing, or generic IPC authority. The production composer will expose a localized non-interactive unavailable state, explain that no project data is sent and that this is not long-term memory, and always allow ordinary chat. Existing lower-level pipeline code and fixtures remain available for later authorized work.

## Explicit exclusions

No redesign, Agent, Computer Use, Browser, Swiss Knife, patch execution, cloud inference, network access, download, Vault read, repository-to-model context, arbitrary filesystem access, shell, or new IPC.
