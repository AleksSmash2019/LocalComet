# LocalComet — Architecture

## Контур продукта (desktop)
```
Svelte 5 UI ──(Tauri IPC, 49 commands)──> Rust src-tauri
                                              │  ControlPlaneBridge / DesktopSidecarSupervisor
                                              ▼  localcomet.ipc/1.0 (len-prefix 4-byte BE, ≤4 MiB)
                                       Python sidecar
                                              │  Control Plane → Model Gateway
                                              ▼
                                       Managed llama.cpp runtime (GGUF, SHA-256 verified)
```

### Слои
- **UI** (`desktop/localcomet-desktop/src/lib`): components, stores, bridge, i18n. Не показывает ложное состояние (INV-UI-001).
- **Rust** (`src-tauri/src`): `lib.rs` (command registry + startup phases), `control_plane.rs`, `artifact_trust.rs` (catalog/download/verify/storage), `managed_runtime.rs` (llama.cpp lifecycle), `approval*.rs`, `files.rs`, `workspace.rs`.
- **Python** (`modules/`, `core/`, `agents/`): 134 модуля. Control plane, model gateway, knowledge, files policy, tool execution (ADR-013/015).
- **Skills** (`modules/skills/`) — НОВЫЙ контур: manifest, lifecycle, permissions, sandbox-runner. См. SECURITY.md §3.

### Источники истины
- Риски: `security/invariants/tool_risk_levels.toml` (`read_only`/`guarded`/`dangerous`).
- Инварианты: `security/invariants/invariants.toml`.
- Каталог артефактов: embedded, hash-pinned (INV-CATALOG-001).

### IPC
`localcomet.ipc/1.0`, length-prefix 4-byte big-endian, max 4 MiB. Readiness = активный probe, не self-report.

### Legacy (вне продукта, кандидаты на изоляцию — A-03)
`next/app_v5.py`, `agent.py`, `app.py`, `LocalComet_Control_Panel.py`, `LocalComet_Patch_Panel.py` — дублирующие CLI/Tkinter-пути, НЕ часть desktop-продукта.

## Границы модулей
- UI не вызывает huggingface.co напрямую — только через Rust `hf_catalog.rs` (host allowlist, no-redirect/no-proxy).
- Любой guarded/dangerous вызов — только через approval envelope.
- Skill не импортирует приватные модули host; общается через объявленный IPC-контракт.
