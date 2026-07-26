# Инварианты и политики

`status = active` в TOML означает декларацию, не доказательство прохождения. Свежий фактический вывод находится в `30-gates.txt`; все запущенные проверки завершились с exit code 0. Non-authorities перечислены в `security/invariants/non_authorities.toml`: LLM output, имя/metadata файла, app-data/SQLite, frontend state, открытый порт, self-report без active probe, предыдущий прогон, Markdown, логи и cache не являются текущим доказательством.

## Реестр `invariants.toml`

| ID | Формулировка / реализация | Свежий статус 2026-07-26 |
|---|---|---|
| `INV-PROCESS-001` | Desktop владеет sidecar tree через Job Object с `KILL_ON_JOB_CLOSE`, `ACTIVE_PROCESS_LIMIT=1`; `windows_job.rs`, `supervisor.rs` | Bound Rust tests прошли; общий Rust итог: `148 passed; 0 failed; 6 ignored` |
| `INV-READINESS-001` | Ready только после correlated `desk-health-{seq}` с `payload.status=ok`; hello недостаточно; `supervisor.rs` | Shape/failure tests прошли. Real-sidecar test может завершиться как internal SKIP без env, поэтому реальный launch этим результатом не доказан |
| `INV-IPC-001` | 4-byte BE length, max 4 MiB, zero/oversize reject; `ipc.rs` | Bound framing tests прошли |
| `INV-IPC-002` | Bounded stdin retry/timeout; failure terminates sidecar and fails pending requests; `windows_job.rs`, `supervisor.rs` | 4 bound tests прошли |
| `INV-CATALOG-001` | Catalog embedded, SHA-256-pinned, canonical JSON; `artifact_trust.rs` | `active`, но `test_ids=[]`; есть смежные Rust tests, dedicated registry binding отсутствует |
| `INV-CATALOG-002` | LLM/filename/app-data не заменяют catalog digest; `artifact_trust.rs`, `non_authorities.toml` | `active`, `test_ids=[]`; related exact-byte/app-data test прошёл, dedicated binding нет |
| `INV-MODEL-001` | Install/launch требуют size, GGUF magic, catalog SHA-256 и post-open revalidation; `artifact_trust.rs` | `active`, `test_ids=[]`; dedicated registry binding нет |
| `INV-PROCESS-002` | Sidecar запускается `-I -B` и без token/secret/user-site environment; `supervisor.rs` | 2 bound tests прошли |
| `INV-UI-001` | UI не генерирует ready/running/installed/success, `Math.random` или timer progress | `OK: no fake-state violations in 79 frontend file(s) (INV-UI-001)` |
| `INV-EVIDENCE-001` | Evidence содержит tree digest, argv, exit code, versions, timestamp; stale не доказательство | Refresh: tree `9c6662fbc45a18b3...`, 286 source files, 4 outputs OK; provenance: `OK: 4 evidence file(s) fresh and intact...`. Named test `check_evidence_provenance_detects_stale` не найден как test definition |
| `INV-APPROVAL-001` | guarded/dangerous должны атомарно пройти `execute_approved`, scope check и one-time consume | 7 bound approval tests прошли, но product command paths не потребляют grant и `execute_approved` не dispatches tool; end-to-end invariant не доказан |
| `INV-APPROVAL-002` | CSPRNG >=256-bit, scoped, one-time, constant-time comparison | Bound token tests прошли |
| `INV-WORKSPACE-001` | `workspace.set` IPC round-trip, invalidation old tokens, fs blocked during transition | Реестр: `planned`, implementation/test lists пусты; end-to-end не реализован |
| `INV-VALIDATION-CACHE-001` | Persistent cache reuses a successful large-asset digest only for exact format/catalog/path/size/mtime/expected/observed match; model GGUF and the largest catalog-required runtime asset only | `implemented`; cache failure/miss hashes normally. Declared boundary: same-size replacement with an exactly restored previous mtime is accepted from cache until another key field changes, explicit invalidation occurs, or `LOCALCOMET_FORCE_FULL_VALIDATION=1` forces hashing. Bound tests are listed in `security/invariants/invariants.toml` |

## Tool risk policy

Авторитетный файл: `security/invariants/tool_risk_levels.toml`. Допустимы ровно `read_only`, `guarded`, `dangerous`.

| Tool | Risk | Approval | Implementation |
|---|---|---:|---|
| `files.read` | `read_only` | false | `modules/files.py::read_file` |
| `files.list` | `read_only` | false | `modules/files.py::list_files` |
| `files.write` | `guarded` | true | `modules/files.py::write_file` |
| `files.create_folder` | `guarded` | true | `modules/files.py::create_folder` |
| `files.delete` | `dangerous` | true | `modules/files.py::delete_path` |
| `artifact.download` | `guarded` | true | `start_approved_artifact_download` |
| `artifact.remove` | `dangerous` | true | `remove_managed_model` |
| `runtime.start` | `guarded` | true | `managed_runtime_start` |
| `runtime.stop` | `guarded` | true | `managed_runtime_stop` |
| `model.binding.set` | `guarded` | true | `model_binding_set` |

Fresh checker: `OK: 5 tool function(s) classified (3 mutating, all requiring approval); 10 registry entries valid`. Limitation: implementation introspection covers `modules/files.py` functions using `safe_path()`; desktop rows are schema/value checked, not proven to consume approval.

## Trust-chain and parity policies

- Byte trust chain: `OK: 15 trust-chain files pass byte invariants`.
- Tauri parity: `OK: 42 commands registered and invoked (parity holds)`. This is name-set equality in `scripts/check_command_parity.py`, not proof that every bridge wrapper is production-reachable.
- Artifact catalog is embedded/hash-pinned/canonical (`INV-CATALOG-001`); app-data, filenames and model/provider claims cannot approve bytes.
- UI has no authority to assert backend state (`INV-UI-001`). The checker is syntactic and does not detect every semantic demo/mock path.

## CI policy actually present

`.github/workflows/validation.yml` runs on push/PR/manual: a Python pytest subset with a documented ignore-list, Rust test/clippy/fmt, and frontend vitest/svelte-check. Python CI does not run the full repository test set; the ignore-list explicitly records pre-existing failures/fixture requirements.
