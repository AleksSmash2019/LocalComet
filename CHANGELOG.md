# Changelog

All notable changes to LocalComet are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [6.84.6] - 2026-07-25

Best-of-Two Wiring Sprint: подключение security-ядра (перенесённого из параллельной
реализации Local Agent Desktop) к продуктовому пути LocalComet.
Ветка: `integration/best-of-two-local-agent` (7 коммитов, `4fa48fe`…`8b23f8c`).

### Added

- Approval enforcement: CSPRNG 256-bit scoped one-time tokens
  (`src-tauri/src/approval.rs`, `src-tauri/src/approval_commands.rs`) — atomic
  `execute_approved`, TTL sweep, execution-grant expiry (15 тестов).
- Rust workspace authority (`src-tauri/src/workspace.rs`) + переиспользуемый примитив
  `modules/workspace_policy.py`; IPC-схема `workspace.set`.
- Гейты: `check_tool_risk_registry.py`, `check_command_parity.py` (42/42),
  `check_ui_fake_state.py`, `check_evidence_provenance.py`, `check_real_sidecar_tests.py`,
  `tests/test_trust_chain_invariants.py` (все injection-proven).
- In-process smoke (`scripts/smoke_test.py`, 8 шагов) + `localcomet_test_harness.py`.
- Preflight `scripts/doctor.py` + `scripts/build.sh` (7-step fail-fast).
- Реестры инвариантов: `security/invariants/invariants.toml` (12),
  `non_authorities.toml` (16), `tool_risk_levels.toml` (5 инструментов).
- Документация: `docs/engineering/best-of-two-final-report.md`,
  `best-of-two-migration-matrix.md`, `docs/unverified-ledger.md`, `audit/AUDIT_GUIDE.md`.

### Changed

- Активированы инварианты: INV-APPROVAL-001, INV-APPROVAL-002, INV-EVIDENCE-001,
  INV-UI-001 (с `verification_method`).
- `.gitattributes` усилен для trust-chain файлов.
- Real-sidecar тесты: silent skip заменён на honest panic при
  `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`.

### Fixed

- CRLF→LF в `config.py`, `approved-artifacts.v1.json` (trust-chain byte invariants).

### Security

- Нет approval bypass: guarded tools исполняются только через atomic `execute_approved`.
- Критические дефекты donor не унаследованы (approval bypass, dual IPC transport,
  readiness «любой кадр», не дренируемый stderr).
- Ключевая находка: desktop sidecar не исполняет file-tools; enforcement живёт в Rust.

### Build

- Windows NSIS-инсталлятор собирается: `LocalComet_6.84.6_x64-setup.exe`
  (13.32 MB, SHA-256: `7fc82beb3ff74a3ae5ad55b8b365dbd00acd92d81a007f74c1fb0c5dcbfa488f`).

### Commits

- `4fa48fe` feat(approval): CSPRNG scoped one-time tokens + product wiring
- `822575e` feat(workspace): WorkspacePolicy primitive + IPC schema workspace.set
- `4a69094` chore(audit): invariant registries + trust-chain and evidence gates
- `cddd0e8` test(sidecar): honest real-sidecar skip + in-process smoke harness
- `4b0418e` build: preflight doctor.py + build.sh pipeline
- `36af461` docs: best-of-two final report, unverified ledger, audit guide
- `8b23f8c` chore(invariants): activate INV-APPROVAL-001/002, INV-EVIDENCE-001; verify INV-UI-001
