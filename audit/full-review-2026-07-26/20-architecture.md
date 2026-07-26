# Фактическая архитектура

Состояние описано по текущим байтам рабочего дерева 2026-07-26, включая незакоммиченные изменения. Старые README местами описывают меньшую поверхность команд; фактическая регистрация находится в `desktop/localcomet-desktop/src-tauri/src/lib.rs:211-254`.

## Компоненты и границы

```text
Svelte 5 / SvelteKit static UI (WebView2)
  -> @tauri-apps/api invoke/listen
  -> Tauri 2 Rust commands
  -> ControlPlaneBridge / DesktopSidecarSupervisor
  -> localcomet.ipc/1.0: JSON, 4-byte big-endian length, max 4 MiB
  -> isolated Python sidecar
  -> DesktopControlPlane / LocalModelGateway
  -> loopback HTTP 127.0.0.1:<port>/v1
  -> managed llama.cpp or an external OpenAI-compatible local provider
```

- Native entry: `desktop/localcomet-desktop/src-tauri/src/main.rs:3-4`.
- Tauri setup/state/handler registration: `src-tauri/src/lib.rs:80-255`.
- UI entry: `src/routes/+page.svelte:2-5`; root shell: `src/lib/components/shell/AppShell.svelte`.
- Typed UI bridges: `src/lib/bridge/{controlPlane,modelGateway,files,knowledge,knowledgeReview,approval}.ts`.
- Rust framing: `src-tauri/src/ipc.rs:3-72`; Python frame loop: `tools/run_localcomet_desktop_sidecar.py:112-137`.
- Python dispatch: `modules/desktop_sidecar_runtime_ru.py:128-170,238-304`.
- Model HTTP/SSE adapter: `modules/local_model_gateway_ru.py:1045-1058,1131-1330`.
- WebView CSP allows self/Tauri IPC, not arbitrary model ports: `src-tauri/tauri.conf.json:30-32`.

The repository also contains a larger legacy Python agent (`core/`, `agents/`, `modules/`, `next/`, Tkinter entry points). The desktop product path above uses only the bounded desktop sidecar surface; presence of legacy modules does not make them callable from the WebView.

## Startup lifecycle

1. `main()` calls `localcomet_desktop_lib::run()` (`main.rs:3-4`).
2. Rust acquires the single-instance guard; a duplicate exits (`lib.rs:52-78`). The configured main window starts hidden (`tauri.conf.json:14-28`).
3. `.setup()` resolves the application-data root, creates the embedded-catalog trust service, supervisor and bridge, installs the frame router, starts the sidecar and waits at most eight seconds (`lib.rs:81-149`).
4. Debug launch is fixed Python `-I -B tools/run_localcomet_desktop_sidecar.py`; release uses packaged `localcomet-core.exe` (`supervisor.rs:12-20,106-170`). stdin/stdout/stderr are redirected and a desktop hello is sent (`supervisor.rs:263-296`).
5. Readiness requires a correlated `desk-health-{sequence}` response with `payload.status == "ok"`, plus the `python_core` hello and a live process (`supervisor.rs:299-321,360-372,517-542`).
6. Only after readiness are managed Tauri states installed and the hidden window shown (`lib.rs:150-196`).
7. `AppShell` initializes Control Plane, model gateway, artifact acquisition and knowledge subscriptions on mount (`AppShell.svelte:149-160`).
8. Window close stops managed model runtime, then sidecar (`lib.rs:198-209`). Sidecar shutdown sends `app.shutdown`, waits 1.5 seconds and terminates if necessary (`supervisor.rs:403-443`).

## User prompt to model answer

1. `MessageComposer.svelte:54-73` calls `startLocalModelTurn(draft, conversationId, includedFileIds)`.
2. `stores/modelGateway.ts:680-770` rejects concurrent/unready submissions, verifies the managed session, creates a 24-hex request ID, records identity and calls `model_turn_start`.
3. `bridge/modelGateway.ts:154-193` sends request/session/model IDs, timestamp, token bound, prompt, selected file IDs, locale and binding fingerprint.
4. `control_plane.rs:2029-2142` validates every field, rereads selected files through the bounded `SelectedFilesManager`, appends rendered context, reserves the request, rechecks managed readiness and sends `model.turn.start` over IPC.
5. `desktop_sidecar_runtime_ru.py:266-304` validates and dispatches to `LocalModelGateway.start_turn()`.
6. `local_model_gateway_ru.py:472-559` validates exact payload keys, binding/model identity and concurrency, then starts one worker. It posts bounded, text-only streaming requests to `/v1/chat/completions` with temperature 0 (`:1131-1202,1432-1450`). SSE has line/event/output/time bounds (`:1154-1166,1237-1330`).
7. Python emits `model.turn.started`, zero or more `model.output.delta`, and one terminal event (`completed`, `cancelled`, `timed_out`, or `failed`) (`:713-799`).
8. Rust validates/correlates frames and emits `localcomet://control-plane-event` (`supervisor.rs:486-514`; `control_plane.rs:1496-1544`).
9. `stores/modelGateway.ts:884-975` verifies request, session, model, binding and sequence before appending output.

Trusted assistant capabilities mark internet, browser, filesystem, Vault, shell and tools unavailable (`local_model_gateway_ru.py:202-225`).

## Model connection chain

External provider: UI probes a selected port; Python GETs `127.0.0.1:<port>/v1/models`; binding is allowed only to a model from the current discovery result and remains in memory (`modelGateway.ts:355-397`; `local_model_gateway_ru.py:423-431,1060-1108`).

Managed provider: Rust validates installed runtime/model against the embedded hash-pinned catalog (`artifact_trust.rs:1167-1252`), starts the approved runtime (`managed_runtime.rs:1977-1993`), creates an opaque runtime instance, loopback port and credential, probes readiness, then asks Python to attach that exact instance. Python performs model discovery and one-token inference before `inference_ready=true` (`local_model_gateway_ru.py:612-661`). Every turn carries a binding fingerprint; Rust and UI reject identity drift (`control_plane.rs:2097-2106`; `modelGateway.ts:884-900`). An open port alone is non-authoritative (`security/invariants/non_authorities.toml:49-68`).

## Control Plane events

Canonical Rust UI projection (`control_plane.rs:204-221`): `method`, `sequence`, `reply_to`, optional request/chat/model/session/thread/turn/item IDs, `control_plane_version`, `state`, optional `kind` and `text`, and method-dependent `metadata`.

Accepted general methods are `sidecar.status`; `session.created/closed`; `thread.created`; `turn.started/completed/cancelled/failed`; `item.started/delta/completed`; and model `started/output.delta/completed/cancelled/timed_out/failed` (`bridge/controlPlane.ts:101-129`; `types/controlPlane.ts:15-32`). General sequences are tracked per `reply_to` (`stores/controlPlane.ts:55,156-162`); model events add strict identity/fingerprint/consecutive-sequence checks. `metadata` is not one universal object; model-specific validation is in `control_plane.rs:2786-2859`.

## Security boundaries and known gap

- Windows Job Object: `KILL_ON_JOB_CLOSE`, active-process limit 1 (`windows_job.rs:373-380,505-506`).
- Sidecar: Python `-I -B`, bounded writes, minimal environment without token/secret inheritance (`supervisor.rs:12-22,332-357,667-697`).
- Artifact authority: embedded catalog digest plus local size/hash/magic/path checks; filenames, app-data and provider metadata are non-authorities.
- Frontend state is non-authoritative; readiness/success must come from backend evidence (`invariants.toml:124-137`).
- Main capability is a fixed command allowlist plus event listen/unlisten (`src-tauri/capabilities/main.json:8-50`).

The authoritative registry says artifact download/removal, runtime start/stop and model binding require approval. Current exposed paths accept `confirmed: bool` or no grant, and do not consume an `execute_approved()` token. `execute_approved()` returns grant metadata but does not dispatch a tool (`approval_commands.rs:100-135`). This is an incomplete end-to-end enforcement boundary, not a proven approval gate.
