# Все Tauri-команды

Найдено 42 `#[tauri::command]`; все 42 зарегистрированы в `src-tauri/src/lib.rs:211-254`. Риск указан только при наличии записи в `security/invariants/tool_risk_levels.toml`; `не классифицирован` означает отсутствие авторитетной записи, а не безопасность. `State`/`WebviewWindow` как framework-injected входы опущены.

| Команда | Rust-файл:строка | Явный вход | Выход | Прямой UI invoke | Риск |
|---|---|---|---|---|---|
| `control_plane_bootstrap` | `control_plane.rs:1842` | нет | `Result<Value, BridgeError>` | `bridge/controlPlane.ts:17` | не классифицирован |
| `control_plane_create_session` | `control_plane.rs:1851` | `title: String` | `Result<Value, BridgeError>` | `controlPlane.ts:21` | не классифицирован |
| `control_plane_close_session` | `control_plane.rs:1860` | `session_id: String` | `Result<Value, BridgeError>` | `controlPlane.ts:25` | не классифицирован |
| `control_plane_create_thread` | `control_plane.rs:1872` | `session_id, title: String` | `Result<Value, BridgeError>` | `controlPlane.ts:29` | не классифицирован |
| `control_plane_start_mock_turn` | `control_plane.rs:1886` | `thread_id, prompt, behavior: String` | `Result<Value, BridgeError>` | `controlPlane.ts:33` | не классифицирован |
| `control_plane_get_turn_status` | `control_plane.rs:1907` | `turn_id: String` | `Result<Value, BridgeError>` | `controlPlane.ts:37` | не классифицирован |
| `control_plane_cancel_turn` | `control_plane.rs:1919` | `turn_id, reason: String` | `Result<Value, BridgeError>` | `controlPlane.ts:41` | не классифицирован |
| `model_gateway_catalog` | `control_plane.rs:1941` | нет | `Result<Value, BridgeError>` | `bridge/modelGateway.ts:37` | не классифицирован |
| `model_gateway_probe` | `control_plane.rs:1953` | `port: u16` | `Result<Value, BridgeError>` | `modelGateway.ts:41` | не классифицирован |
| `model_gateway_list_models` | `control_plane.rs:1970` | `port: u16` | `Result<Value, BridgeError>` | `modelGateway.ts:45` | не классифицирован |
| `model_binding_set` | `control_plane.rs:1984` | provider/harness/model IDs, `port`, `confirmed`, runtime ID | `Result<Value, BridgeError>` | `modelGateway.ts:68` | `guarded`, approval required |
| `model_turn_start` | `control_plane.rs:2029` | request/chat/model IDs, prompt, locale, fingerprint, timestamp, max tokens, file IDs | `Result<Value, BridgeError>` | `modelGateway.ts:172-182` | не классифицирован |
| `model_turn_cancel` | `control_plane.rs:2145` | `request_id: String` | `Result<Value, BridgeError>` | `modelGateway.ts:216` | не классифицирован |
| `knowledge_review_list` | `control_plane.rs:2157` | `offset, limit: u16` | `Result<Value, BridgeError>` | `bridge/knowledgeReview.ts:101` | не классифицирован |
| `knowledge_review_get` | `control_plane.rs:2167` | artifact identity | `Result<Value, BridgeError>` | `knowledgeReview.ts:120` | не классифицирован |
| `knowledge_review_snapshot` | `control_plane.rs:2176` | нет | `Result<Value, BridgeError>` | `knowledgeReview.ts:147` | не классифицирован |
| `knowledge_review_refresh` | `control_plane.rs:2183` | нет | `Result<Value, BridgeError>` | `knowledgeReview.ts:147` | не классифицирован |
| `knowledge_review_decision_create` | `control_plane.rs:2190` | 9 strings, optional change identity | `Result<Value, BridgeError>` | `knowledgeReview.ts:166-177` | не классифицирован |
| `knowledge_turn_preview` | `knowledge.rs:9` | turn/intent, max chars/results | `Result<Value, BridgeError>` | `bridge/knowledge.ts:28-33` | не классифицирован |
| `knowledge_turn_decide` | `knowledge.rs:42` | turn/injection/hash/action | `Result<Value, BridgeError>` | `knowledge.ts:44-49` | не классифицирован |
| `managed_runtime_catalog` | `artifact_trust.rs:1182` | нет | `ManagedRuntimeCatalog` | `modelGateway.ts:77` | не классифицирован |
| `managed_model_catalog` | `artifact_trust.rs:1189` | нет | `ManagedModelCatalog` | `modelGateway.ts:81` | не классифицирован |
| `managed_installed_artifacts` | `artifact_trust.rs:1194` | нет | `Result<ManagedInstalledArtifacts, BridgeError>` | `modelGateway.ts:85` | не классифицирован |
| `managed_artifact_validation_status` | `artifact_trust.rs:1212` | `artifact_id: String` | `Result<ArtifactValidationSummary, BridgeError>` | `modelGateway.ts:127` | не классифицирован |
| `managed_model_readiness` | `artifact_trust.rs:1235` | `model_id: String` | `Result<ModelReadinessSummary, BridgeError>` | `modelGateway.ts:136` | не классифицирован |
| `list_approved_downloadable_artifacts` | `artifact_acquisition.rs:799` | нет | `Vec<ApprovedDownloadableArtifact>` | `modelGateway.ts:89` | не классифицирован |
| `start_approved_artifact_download` | `artifact_acquisition.rs:806` | artifact ID, `confirmed: bool` | `Result<ArtifactDownloadState, BridgeError>` | `modelGateway.ts:96` | `guarded`, approval required |
| `get_artifact_download_state` | `artifact_acquisition.rs:815` | `job_id: String` | `Result<ArtifactDownloadState, BridgeError>` | `modelGateway.ts:104` | не классифицирован |
| `cancel_artifact_download` | `artifact_acquisition.rs:823` | `job_id: String` | `Result<ArtifactDownloadState, BridgeError>` | `modelGateway.ts:110` | не классифицирован |
| `remove_managed_model` | `artifact_acquisition.rs:831` | model ID, `confirmed: bool` | `Result<ManagedModelRemovalResult, BridgeError>` | `modelGateway.ts:117` | `dangerous`, approval required |
| `managed_runtime_status` | `managed_runtime.rs:1960` | нет | `Result<ManagedRuntimeStatus, BridgeError>` | `modelGateway.ts:73` | не классифицирован |
| `managed_runtime_start` | `managed_runtime.rs:1977` | `model_id: String` | `Result<ManagedRuntimeStartResponse, BridgeError>` | `modelGateway.ts:143` | `guarded`, approval required |
| `managed_runtime_stop` | `managed_runtime.rs:1995` | нет | `Result<ManagedRuntimeStopResponse, BridgeError>` | `modelGateway.ts:147` | `guarded`, approval required |
| `managed_runtime_logs` | `managed_runtime.rs:2009` | нет | `ManagedRuntimeLogs` | `modelGateway.ts:151` | не классифицирован |
| `files_capability_status` | `files.rs:556` | нет | `FilesCapabilityStatus` | `bridge/files.ts:21` | не классифицирован |
| `select_files` | `files.rs:571` | нет; native window injected | `Result<FileSelectionResponse, FileCapabilityError>` | `files.ts:25` | не классифицирован |
| `list_selected_files` | `files.rs:589` | нет | `Result<Vec<SelectedFileSummary>, FileCapabilityError>` | `files.ts:29` | не классифицирован |
| `preview_selected_file` | `files.rs:596` | `file_id: String` | `Result<SelectedFilePreview, FileCapabilityError>` | `files.ts:34` | не классифицирован |
| `forget_selected_file` | `files.rs:604` | `file_id: String` | `Result<Vec<SelectedFileSummary>, FileCapabilityError>` | `files.ts:40` | не классифицирован |
| `request_approval` | `approval_commands.rs:72` | tool, JSON input | `Result<String, BridgeError>` | `bridge/approval.ts:17` | не классифицирован |
| `execute_approved` | `approval_commands.rs:108` | token, tool, JSON input | `Result<Value, BridgeError>` | `approval.ts:29` | не классифицирован |
| `set_workspace` | `approval_commands.rs:141` | `path: String` | `Result<Value, BridgeError>` | `approval.ts:42` | не классифицирован |

## Фактическая достижимость

- Компоненты не вызывают Tauri напрямую; `invoke` сосредоточен в шести bridge-модулях.
- Control Plane store использует bootstrap/session/thread/mock-turn/status/cancel; wrapper `close_session` не имеет найденного high-level caller.
- `managed_artifact_validation_status` имеет wrapper, но найденного store/component caller нет.
- `approval.ts` имеет wrappers, но не импортируется production Svelte/store кодом. Эти три команды также отсутствуют в `capabilities/main.json`, поэтому разрешение главному WebView не доказано.
- Registry классифицирует только 5 из 42 Tauri-команд. Переносить уровни `files.read/list/...` с `modules/files.py` на Tauri file-picker команды оснований нет.
