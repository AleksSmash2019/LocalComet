# OR-01 — Architecture owner ratification

**Decision ID:** `OR-01`

**Accountable owner:** `AleksSmash2019`

**Decision source:** explicit repository-owner instruction in mission `UP00-WP01_WINDOWS_ONE_CLICK_LAUNCH`

**Effective date:** `2026-07-20`

**Effect:** prospective only

## Decision

The Architecture Governance Pack `1.0.4-correction-candidate`, including the Architecture Constitution identified inside that pack as `LC-AGP-CONSTITUTION`, is ratified prospectively for new LocalComet work. The Constitution has the highest normative precedence.

This decision does not retroactively prove that existing LocalComet code conforms. Candidate and advisory statuses inside the immutable input packages remain historical facts; this repository record supplies the later accountable human decision those packages could not supply themselves.

The source-mapping decision is:

```yaml
source_mapping_status: COMPLETED_AND_REMEDIATED
source_mapping_baseline_commit: 6c784ace543e345bdb8bd2f778be974dc89f2df5
```

The Universal Patches UP00-UP10 package `1.0.3-correction-candidate` is adopted as the long-term development roadmap. Roadmap adoption grants no blanket implementation authority.

The only source-writing work package authorized by OR-01 is:

`UP00-WP01 — Windows One-Click Launch and Installer Baseline`

Implementation authority for UP01-UP10 is `NONE`.

## Immutable inputs

| Input | SHA-256 |
|---|---|
| Universal Patches UP00-UP10 `1.0.3-correction-candidate` | `95e35bf21f1c3af5a44db9f9944ddad01e3e5265cc40812cac9d733b59721f29` |
| Architecture Governance Pack `1.0.4-correction-candidate` | `3dc9fd1434c68462352fe493ffbd640a7ef30911d299043be7f2b1ebc6c1b607` |
| Cross-Pack Dossier `1.4.0` | `155f7856db8208b997722cae1c1f5eca86cfefcfd1ec07ce73a1c49883a1873b` |

## Normative precedence used

For this work package, the applicable order is:

1. the ratified Architecture Constitution;
2. accepted constitutional decisions, if any;
3. ratified Architecture Governance Pack rules;
4. its dependency and quality-gate definitions;
5. its Codex protocol and mandatory templates;
6. accepted repository-specific owner and source-mapping evidence;
7. the adopted Universal Patch protocol and shared catalog;
8. accepted patch-specific decisions;
9. this separately authorized work package;
10. implementation.

The explicit owner mission is the patch-specific source-write authorization. It narrows the roadmap to UP00-WP01 and does not amend the Constitution.

## Deferred decisions

OR-01 does not decide or authorize:

- G03/G12 architectural decomposition;
- G05 IPC or contract versioning;
- G09 data lifecycle;
- public-release licensing;
- production performance baselines;
- production code signing;
- automatic updates;
- automated governance-enforcement activation.

UP00-WP01 must stop if it cannot be completed without one of these decisions.

## Required safeguards

- Preserve the existing Svelte/Tauri/Rust/Python trust and IPC boundaries.
- Keep Rust as the process and native-window enforcement boundary.
- Make no Vault, user-data, schema, migration, or ownership change.
- Add no generic shell, raw IPC, publication, approval, telemetry, update, or network authority.
- Produce reviewable commits, independent evidence inputs, bounded rollback evidence, and an unsigned internal installer only.
- Do not push, create a remote pull request, or modify `main`.

## Separate enforcement status

Ratification makes the Constitution and Governance Pack normative for this new work. OR-01 does not claim that automated repository-wide enforcement has been prepared or activated. Any such activation remains a separate accountable decision.
