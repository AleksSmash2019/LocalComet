# ЧАСТЬ A — Targeted fixes по аудиту MVP-P0-C-A2 (2026-08-04)

**Исполнитель:** OpenCode
**Ветка:** `feature/donor-ui-compatible-port` (не переключал, коммитов не делал)
**Основание:** `audit/2026-08-04/mvp-p0c-a2-brief.md`, разделы 2.1 (E1/E2/E6) и 3.4
**Скоуп правок:** `desktop/localcomet-desktop/src-tauri/src/files.rs`,
`desktop/localcomet-desktop/src-tauri/src/control_plane.rs` — ровно те два файла,
которые названы в задании.

> Замечание о границах: AGENTS.md запрещает трогать `src-tauri/`, «если задача не
> говорит об этом прямо». Задание называет `files.rs` и `control_plane.rs` прямо,
> поэтому правки внесены только в них. `approval_commands.rs` не изменён вообще
> (digest-правка оказалась не нужна в нём — см. §3.1),
> `TOOL_EXECUTION_ACTIVATION_ENABLED` не тронут, orchestration loop /
> ApprovalCard mounting / live tool execution не добавлялись,
> `bridge.py`, `notion-bridge.mjs`, Vault, Projects, BrowserProfile не тронуты.

---

## 1. Исходное состояние

`git status --porcelain --branch` до начала работы:

```
## feature/donor-ui-compatible-port
?? .ci-venv-diag/
?? audit/2026-08-04/
```

HEAD: `e300373 fix(rust): resolve Windows 8.3 short-path aliases in comparable_path`.
Ранее незакоммиченных правок в исходниках не было (untracked — только диагностический
venv и папка текущего аудита, в которой лежал `mvp-p0c-a2-brief.md`). Часть работы
предыдущим прогоном не сделана: `resolve_short_path` был в silent-fallback виде,
wire digest для `model.turn.start` отсутствовал как таковой.

---

## 2. Fix 1 + 2 — `files.rs`: `resolve_short_path` fail-closed и тесты E1/E2/E6

### 2.1 Обоснование

`comparable_path` — единственный нормализатор путей для четырёх сравнений
безопасности:

| Строка | Сравнение | Что защищает |
|---|---|---|
| `files.rs:625` | `comparable_path(path) != comparable_path(&canonical)` | «Selected path alias was rejected» |
| `files.rs:633` | `comparable_path(&final_path) != comparable_path(&canonical)` | «Selected path identity was rejected» |
| `files.rs:679`/`683` (в `read_record`) | `canonical`/`final_path` vs `record.path` | `LC_FILE_CHANGED` при подмене |
| `files.rs:365`/`401` | alias-дедуп при регистрации | отказ от дублей/алиасов |

При `GetLongPathNameW == 0` (E1) или переполнении буфера (E2) старый код возвращал
`Ok(path.to_owned())` — то есть **ненормализованную 8.3-строку**. Две спеллинга
одного файла (`LONGFI~1.TXT` и `longfilename.txt`) в этом состоянии сравниваются как
разные, а сравнения выше построены на равенстве ключей. Это класс E6: дрейф сравнения,
через который 8.3-алиас может обойти проверку «путь после canonicalize/reparse-фильтров
совпадает с тем, что дал handle». Фейл-открытый путь в security-компараторе
недопустим, поэтому оба исхода теперь `Err(access_denied())` (`LC_FILE_ACCESS_DENIED`).

Проверено, что fail-closed не ломает продуктовые пути: во всех callsites
`comparable_path` вызывается **после** успешного `fs::canonicalize` (и, для
`final_path`, на пути открытого хэндла), то есть путь существует и
`GetLongPathNameW` для него отрабатывает. Два места (`files.rs:380`, `files.rs:388`)
уже используют `.ok()` и деградируют как «путь неизвестен», без паники и без
ложного равенства.

### 2.2 Diff

```diff
@@ fn comparable_path(path: &Path) -> Result<String, FileCapabilityError> {
     Ok(resolved.trim_end_matches('\\').to_ascii_lowercase())
 }

+#[cfg(windows)]
+const LONG_PATH_BUFFER_UTF16_UNITS: usize = 1024;
+
+/// Fail-closed interpretation of a `GetLongPathNameW` result.
+///
+/// `GetLongPathNameW` returns 0 on failure (missing path, denied path, invalid
+/// path) and returns the required buffer length when the supplied buffer is too
+/// small. In both cases the 8.3 short-name alias was NOT resolved, so returning
+/// the unresolved input would let an 8.3 alias reach the alias comparisons in
+/// `validate_explicit_selection` and `read_record` un-normalized, where two
+/// spellings of the same file can compare unequal (or an alias of a rejected
+/// location can compare equal to an accepted one). Both outcomes deny access.
+#[cfg(windows)]
+fn interpret_long_path_result(
+    returned_units: u32,
+    buffer: &[u16],
+) -> Result<String, FileCapabilityError> {
+    let returned = returned_units as usize;
+    if returned == 0 || returned >= buffer.len() {
+        return Err(access_denied());
+    }
+    Ok(String::from_utf16_lossy(&buffer[..returned]))
+}
+
 #[cfg(windows)]
 fn resolve_short_path(path: &str) -> Result<String, FileCapabilityError> {
     use windows_sys::Win32::Storage::FileSystem::GetLongPathNameW;
     let wide: Vec<u16> = path.encode_utf16().chain(std::iter::once(0)).collect();
-    let mut out = vec![0u16; 1024];
+    let mut out = vec![0u16; LONG_PATH_BUFFER_UTF16_UNITS];
     let len = unsafe { GetLongPathNameW(wide.as_ptr(), out.as_mut_ptr(), out.len() as u32) };
-    if len == 0 || len as usize >= out.len() {
-        return Ok(path.to_owned());
-    }
-    out.truncate(len as usize);
-    Ok(String::from_utf16_lossy(&out))
+    interpret_long_path_result(len, &out)
 }
```

Решение о форме: вынесена чистая функция `interpret_long_path_result(returned_units,
buffer)`, потому что иначе E2 (переполнение) невозможно наблюдать в unit-тесте —
синтетически длинный путь падает через E1 (`ERROR_PATH_NOT_FOUND`), а не через границу
буфера. Так граница проверяется детерминированно, без моков Win32.

### 2.3 Добавленные тесты (`#[cfg(windows)]`, в `files::tests`)

- `long_path_resolution_failure_is_fail_closed` — **E1**: `returned_units == 0` →
  `LC_FILE_ACCESS_DENIED`; реальный вызов `resolve_short_path` на несуществующем
  `C:\localcomet-missing-<pid>-<ms>\LONGNA~1.TXT` → `Err`, и `comparable_path` на нём
  тоже `Err` (то есть ошибка доходит до компаратора, а не глотается); positive
  control: `(3, ['a','b','c',0])` → `"abc"`.
- `long_path_buffer_overflow_is_fail_closed` — **E2**: репортнутая длина
  `1024`, `1025`, `u32::MAX` → `LC_FILE_ACCESS_DENIED`; длина `1023` внутри буфера →
  `Ok` длиной 1023 (граница не сдвинута в другую сторону); путь длиной
  > 1024 UTF-16 code units → `Err`.
- `short_alias_and_long_path_share_one_comparable_key_or_are_rejected` — **E6**:
  реальный 8.3-алиас берётся через `GetShortPathNameW`; пока файл существует,
  `comparable_path(alias) == comparable_path(long)` (один ключ сравнения); после
  удаления файла `comparable_path(alias)` и `comparable_path(long)` возвращают
  `LC_FILE_ACCESS_DENIED`, а не сырую 8.3-строку. Если на томе отключена генерация
  8.3, тест честно проверяет только reject-ветку (без skip-обмана: сам reject
  всё равно ассертится).

### 2.4 Явно принятый компромисс

Буфер оставлен 1024 UTF-16 units (как в задании), поэтому путь, длинная форма
которого не влезает в 1024 units, теперь **отклоняется**, а не принимается
ненормализованным. Вариант «перезапросить с требуемой длиной (как
`final_path_for_handle` с 32 768)» рассмотрен и **не** взят: он изменил бы
заявленный в задании порог и наблюдаемое поведение E2. Если владелец захочет
поддержать такие пути, это отдельная правка (retry с `returned_units` в качестве
размера буфера) — она совместима с текущей чистой функцией.

---

## 3. Fix 3 — `control_plane.rs`: `assistant_context` внутри wire digest `model.turn.start`

### 3.1 Что было найдено фактически

Проверка исходников показала: для `model.turn.start` **никакого digest не
существовало вообще** — ни в `control_plane.rs`, ни в `approval_commands.rs`
(последний считает `canonical_input_digest` только для approval-скоупов
artifact/runtime/model-binding/workspace, и `model.turn.start` через него не
проходит). Поэтому «добавить `assistant_context` в существующий расчёт» было
невозможно буквально; правка вводит digest для этого метода и с первого дня
включает в него `assistant_context`. `approval_commands.rs` не изменён.

Дыра, которую это закрывает, конкретна:

1. `model_turn_start` строит `AssistantContext::trusted(...)` и резервирует turn:
   `state.reserve_model_turn(&identity, assistant_context.capabilities.tools.clone())`
   → `permitted_tool_names` в реестре, то есть **весь capability-скоуп turn-а
   выводится из `assistant_context`**.
2. Диспатч (`request_reserved_model_start`) до правки проверял только
   `model_request_reservation_exists(request_id)` — «резервация с таким id есть».
   Байты payload с резервацией не сверялись никак.
3. Acceptance-эхо от сайдкара (`validate_model_acceptance`) покрывает
   `request_id`/`turn_id`/`chat_session_id`/`model_id`/`submitted_at_unix_ms`/
   `max_tokens`/`binding_fingerprint`, и **не** покрывает ни `prompt`, ни
   `assistant_context`.

Итог: резервация, созданная для capability-neutral контекста (`tools: []`), могла
быть использована для отправки payload с другим `assistant_context` — и ни одна
проверка этого не заметила бы. Это ровно тот шаг, который brief просил закрыть
до любого разговора об активации инструментов (§6.3 brief-а).

### 3.2 Diff

```diff
+use crate::approval::canonical_input_digest;
 use crate::artifact_trust::ArtifactTrustService;
 use crate::files::SelectedFilesManager;
```

```diff
 struct ModelRequestEntry {
     ...
     permitted_tool_names: Vec<String>,
     intermediate_tool_calls: Vec<Value>,
+    /// Digest of the canonical `model.turn.start` wire payload this reservation
+    /// authorizes, including `assistant_context`. `None` until the reservation is
+    /// bound (knowledge turns are registered post-dispatch and stay unbound, so
+    /// they can never satisfy the dispatch check).
+    reserved_wire_digest: Option<[u8; 32]>,
 }
```

```diff
 impl ModelRequestRegistry {
     fn insert(...) -> Result<Arc<ModelRequestWatchdog>, BridgeError> { ... }
+
+    fn bind_reserved_wire_digest(
+        &mut self,
+        request_id: &str,
+        wire_digest: [u8; 32],
+    ) -> Result<(), BridgeError> {
+        let entry = self.entries.get_mut(request_id).ok_or_else(|| {
+            BridgeError::new("request_not_found", "model request reservation is missing")
+        })?;
+        if entry.reserved_wire_digest.is_some() {
+            return Err(BridgeError::new(
+                "protocol_mismatch",
+                "model request reservation is already bound",
+            ));
+        }
+        entry.reserved_wire_digest = Some(wire_digest);
+        Ok(())
+    }
 }
```

```diff
+/// Canonical `model.turn.start` wire payload. Single construction site so the
+/// digest that authorizes a turn and the bytes that are framed cannot drift.
+fn model_turn_wire_payload(
+    identity: &ModelRequestIdentity,
+    prompt: &str,
+    assistant_context: &AssistantContext,
+) -> Value {
+    json!({
+        "request_id": identity.request_id,
+        "chat_session_id": identity.chat_session_id,
+        "model_id": identity.model_id,
+        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
+        "max_tokens": identity.max_tokens,
+        "prompt": prompt,
+        "assistant_context": assistant_context,
+        "binding_fingerprint": identity.binding_fingerprint,
+    })
+}
+
+/// Digest over every dispatched `model.turn.start` field, `assistant_context`
+/// (application, conversation and the capability/tool grant) included.
+fn model_turn_wire_digest(payload: &Value) -> [u8; 32] {
+    canonical_input_digest(payload)
+}
+
+/// Fail-closed dispatch guard: the framed payload must hash to the digest the
+/// reservation was created with. A reservation that is missing, unbound, or bound
+/// to different bytes (including a different `assistant_context`) cannot dispatch.
+fn model_request_reservation_authorizes_wire(
+    registry: &Mutex<ModelRequestRegistry>,
+    request_id: &str,
+    wire_digest: &[u8; 32],
+) -> Result<(), BridgeError> {
+    if !model_request_reservation_exists(registry, request_id) {
+        return Err(BridgeError::new(
+            "request_not_found",
+            "model request reservation expired before dispatch",
+        ));
+    }
+    let registry = registry.lock().expect("model request registry poisoned");
+    let Some(entry) = registry.entries.get(request_id) else {
+        return Err(BridgeError::new(
+            "request_not_found",
+            "model request reservation expired before dispatch",
+        ));
+    };
+    match entry.reserved_wire_digest {
+        Some(reserved) if reserved == *wire_digest => Ok(()),
+        _ => Err(BridgeError::new(
+            "protocol_mismatch",
+            "model turn payload does not match the reserved turn",
+        )),
+    }
+}
```

```diff
     fn reserve_model_turn(
         self: &Arc<Self>,
         identity: &ModelRequestIdentity,
         permitted_tool_names: Vec<String>,
+        wire_digest: [u8; 32],
     ) -> Result<(), BridgeError> {
-        let watchdog = self
-            .model_requests
-            .lock()
-            .expect("model request registry poisoned")
-            .insert(identity.clone(), permitted_tool_names)?;
+        let watchdog = {
+            let mut registry = self
+                .model_requests
+                .lock()
+                .expect("model request registry poisoned");
+            let watchdog = registry.insert(identity.clone(), permitted_tool_names)?;
+            if let Err(error) =
+                registry.bind_reserved_wire_digest(&identity.request_id, wire_digest)
+            {
+                registry.remove(&identity.request_id);
+                return Err(error);
+            }
+            watchdog
+        };
```

```diff
     fn request_model_turn_reserved(...) -> Result<Value, BridgeError> {
-        let payload = json!({
-            "request_id": identity.request_id,
-            ...
-            "assistant_context": assistant_context,
-            "binding_fingerprint": identity.binding_fingerprint,
-        });
+        let payload = model_turn_wire_payload(&identity, &prompt, &assistant_context);
```

```diff
     fn request_reserved_model_start(...) -> Result<Value, BridgeError> {
         self.ensure_ready()?;
         validate_payload_for_method(ControlPlaneMethod::ModelTurnStart, &payload)?;
+        let wire_digest = model_turn_wire_digest(&payload);
         let transport_id = self.next_request_id();
         ...
-        let reservation_exists =
-            model_request_reservation_exists(&self.model_requests, model_request_id);
-        let send_result = if reservation_exists {
-            self.supervisor
-                .send_ipc_frame(frame)
-                .map_err(|error| BridgeError::unavailable(&error.to_string()))
-        } else {
-            Err(BridgeError::new(
-                "request_not_found",
-                "model request reservation expired before dispatch",
-            ))
-        };
+        let reservation_authorized = model_request_reservation_authorizes_wire(
+            &self.model_requests,
+            model_request_id,
+            &wire_digest,
+        );
+        let send_result = match reservation_authorized {
+            Ok(()) => self
+                .supervisor
+                .send_ipc_frame(frame)
+                .map_err(|error| BridgeError::unavailable(&error.to_string())),
+            Err(error) => Err(error),
+        };
```

```diff
 pub async fn model_turn_start(...) -> Result<Value, BridgeError> {
     ...
-    state.reserve_model_turn(&identity, assistant_context.capabilities.tools.clone())?;
+    // The reservation is bound to the digest of the exact wire payload it
+    // authorizes, assistant_context (and therefore the capability/tool grant that
+    // drives permitted_tool_names) included. Dispatch re-derives this digest.
+    let wire_digest = model_turn_wire_digest(&model_turn_wire_payload(
+        &identity,
+        &prompt,
+        &assistant_context,
+    ));
+    state.reserve_model_turn(
+        &identity,
+        assistant_context.capabilities.tools.clone(),
+        wire_digest,
+    )?;
```

### 3.3 Свойства правки

- **Wire-контракт не изменён.** Ключи payload те же 8 (`ensure_payload_keys` в
  Rust и `TURN_START_PAYLOAD_KEYS` в `modules/local_model_gateway_ru.py` —
  строгие множества). Новое поле в payload сломало бы real-sidecar и
  bundle/inference parity, поэтому digest хранится **только на стороне Rust**,
  в реестре резерваций. Подтверждение: `tools/test_bug1_inference_bundle_parity.py`
  и real-sidecar gate зелёные (см. §4).
- **Canonical digest — не новый примитив.** Используется существующий
  `approval::canonical_input_digest` (SHA-256 над каноникализованным JSON), уже
  покрытый тестами `approval::tests::key_reordering_does_not_change_digest` и
  `value_change_changes_digest`. `approval.rs` не изменён.
- **Fail-closed по трём осям:** резервации нет → `request_not_found`; резервация
  есть, но digest не привязан → `protocol_mismatch`; digest привязан, но payload
  другой (в т.ч. другой `assistant_context`) → `protocol_mismatch`. Повторная
  привязка запрещена (`protocol_mismatch`), то есть digest резервации иммутабелен.
- **Knowledge-turn путь не сломан:** `registry.insert(identity, Vec::new())` в
  `register_knowledge_model_acceptance` регистрирует turn *после* диспатча
  сайдкаром, `reserved_wire_digest` остаётся `None` — такая запись не может
  авторизовать `model.turn.start` вообще. Это строже, чем было.
- **Capability-нейтральность сохранена.** Никаких новых capabilities, инструментов
  и событий; `AssistantContext::trusted` по-прежнему отдаёт `tools: []` и все
  capability-флаги, кроме локального чата/инференса, в `false`.

### 3.4 Что правка НЕ даёт (честная граница)

Digest — это привязка «резервация ↔ отправленные байты» **внутри Rust**. Он не
является подписью, которую проверяет сайдкар, и acceptance-эхо по-прежнему не
покрывает `assistant_context` / `prompt`. Остаточный риск здесь снижен тем, что
сайдкар сам независимо валидирует контекст: `_validate_assistant_context` +
сравнение с `trusted_assistant_context_payload(locale, ...)` в
`modules/local_model_gateway_ru.py` (строки 268–329, 1099) — любой не-доверенный
`assistant_context` отклоняется на приёмной стороне. Полное покрытие
`assistant_context` эхом требует изменения IPC-контракта (новое поле в
acceptance-ответе + правка сайдкара) и в этот скоуп не входило.

### 3.5 Добавленные тесты (`control_plane::tests`)

- `model_turn_wire_digest_covers_assistant_context` — digest стабилен для
  идентичных входов и **меняется** при: `capabilities.tools`,
  `capabilities.filesystem`, `conversation.locale`, `prompt`.
- `model_turn_dispatch_requires_the_reserved_wire_digest` — отсутствующая
  резервация → `request_not_found`; непривязанная → `protocol_mismatch`;
  привязанная и совпадающая → `Ok`; payload с эскалированным
  `assistant_context.capabilities.tools` на той же резервации →
  `protocol_mismatch`; повторная привязка → `protocol_mismatch`.

---

## 4. Список изменённых файлов

```
 desktop/localcomet-desktop/src-tauri/src/control_plane.rs | 258 ++++++++++++++++++---
 desktop/localcomet-desktop/src-tauri/src/files.rs         | 161 ++++++++++++-
 2 files changed, 387 insertions(+), 32 deletions(-)
```

Новые файлы: `audit/2026-08-04/fixes-p0c-a2.md`,
`audit/2026-08-04/hf-integration-design.md` (этот отчёт и дизайн ЧАСТИ B).
Коммитов и переключений ветки не было. Ничего не удалялось. `.exe/.bat/.ps1` не
создавались. npm-зависимости не добавлялись.

---

## 5. Гейты — запущены после правок, последние строки вывода дословно

Frontend (`desktop/localcomet-desktop`):

```
> localcomet-desktop@0.0.0-v6.84.6 check
> svelte-kit sync && svelte-check --tsconfig ./tsconfig.json
svelte-check found 0 errors and 0 warnings
```

```
 Test Files  24 passed (24)
      Tests  364 passed (364)
```

Rust (`desktop/localcomet-desktop/src-tauri`):

```
test result: ok. 468 passed; 0 failed; 6 ignored; 0 measured; 0 filtered out; finished in 1.85s
```

```
cargo fmt --check   → FMT_EXIT=0 (без вывода)
cargo clippy --all-targets --all-features -- -D warnings → Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.25s ; LASTEXITCODE=0
```

Python-гейты (последние строки каждого):

```
[tests/test_check_bundle_parity.py] exit=0 :: Ran 2 tests in 0.004s | OK
[tests/test_evidence_model.py] exit=0 :: OK: 4 evidence file(s) fresh and intact (tree=dddddddddddddddd...)
[tests/test_trust_chain_gate.py] exit=0 :: Ran 1 test in 0.001s | OK
[tests/test_tool_risk_registry_gate.py] exit=0 :: Ran 2 tests in 0.000s | OK
[tests/test_mockdata_import_gate.py] exit=0 :: Ran 2 tests in 0.005s | OK
[tests/test_trust_chain_invariants.py] exit=0 :: OK: 15 trust-chain files pass byte invariants
[scripts/check_command_parity.py] exit=0 :: OK: 43 commands registered and invoked (parity holds)
[scripts/check_tool_risk_registry.py] exit=0 :: OK: 5 console tool function(s) classified (3 mutating, all requiring approval); 5 sidecar tools covered; 10 registry entries valid
[scripts/check_ui_fake_state.py] exit=0 :: OK: no fake-state violations in 80 frontend file(s) (INV-UI-001)
[scripts/check_mockdata_imports.py] exit=0 :: (type-only imports / fallback constants listed, no violations)
[scripts/check_bundle_parity.py] exit=0 :: OK: 146 shipped module(s) match source across 2 location(s) (bundle parity holds)
[tools/test_bug1_inference_bundle_parity.py] exit=0 :: PART A OK: repo gateway accepts the Rust bridge assistant_context | PART B OK: deployed bundle gateway accepts the Rust bridge payload | ALL OK
[tools/test_adr015_tool_parsing.py] exit=0 :: Ran 67 tests in 7.226s | OK (skipped=1)
[tools/test_tool_risk_rust_parity.py] exit=0 :: OK: Rust REGISTERED_MODEL_TOOLS matches Python TOOL_REGISTRY (5 tools) | OK: R4 execution coverage confirmed via SUPPORTED_TOOLS | OK: parser self-tests passed
```

CLI smoke:

```
Results: 8 passed, 0 failed
SMOKE PASSED: real sidecar product path behaves as expected.
```

Real-sidecar gate (require-режим, системный Python
`C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe`,
`LOCALCOMET_TEST_PROJECT_ROOT=C:\Users\DNS\Documents\LocalComet-build-week-clean`,
`LOCALCOMET_REQUIRE_REAL_SIDECAR=1`):

```
OK: real-sidecar tests ran under require mode with no silent skips
```

Evidence (запущены последними, после всех правок):

```
tree_digest: 9f6bd977cf89ffdf24b830f44ea257a1edf2edf99347cbb4f6db2fc15d3b6077 (353 source files)
[OK] evidence/cargo_test.txt exit=0 tree=9f6bd977cf89ffdf...
[OK] evidence/trust_chain.txt exit=0 tree=9f6bd977cf89ffdf...
[OK] evidence/cmd_parity.txt exit=0 tree=9f6bd977cf89ffdf...
[OK] evidence/tool_risk_registry.txt exit=0 tree=9f6bd977cf89ffdf...
evidence refreshed: all gates green
```

```
OK: 4 evidence file(s) fresh and intact (tree=9f6bd977cf89ffdf...)
```

`git status --porcelain --branch` после работы:

```
## feature/donor-ui-compatible-port
 M desktop/localcomet-desktop/src-tauri/src/control_plane.rs
 M desktop/localcomet-desktop/src-tauri/src/files.rs
?? .ci-venv-diag/
?? audit/2026-08-04/
```

Отличия от baseline AGENTS.md (03.08.2026), зафиксированы честно:

- `cargo test`: **468 passed** против baseline 460 — +5 моих тестов, остальное
  расхождение baseline против HEAD `e300373` (baseline записан до него).
- `check_ui_fake_state.py`: **80** frontend-файлов против baseline 81. Frontend
  я не менял (`git diff` затрагивает только два `.rs`-файла); расхождение
  досталось от HEAD, не от этой правки.
- Полный `pytest` не запускался: мандата на правку legacy git-index failures нет
  (как и в baseline).

---

## 6. Что НЕ сделано и почему

1. **`TOOL_EXECUTION_ACTIVATION_ENABLED` не включён.** Прямой запрет задания и
   Block 3 stop point. `supervisor::tests::p0c_tool_activation_remains_false`
   зелёный.
2. **Orchestration loop, ApprovalCard mounting, live tool execution — не
   добавлялись.** Ни одной новой capability, ни одного нового IPC-метода.
3. **`approval_commands.rs` не изменён.** Digest-правка потребовалась в
   `control_plane.rs`, а не в нём (§3.1); менять его без необходимости запрещено.
4. **Acceptance-эхо не расширено `assistant_context`.** Это изменение IPC-контракта
   (Rust + сайдкар + parity-гейты) и отдельный скоуп — см. §3.4.
5. **Буфер long-path не увеличен и retry не добавлен** — см. §2.4.
6. **Коммитов/пушей/переключения ветки нет.**
7. **Полный `pytest` не прогонялся** (см. §5).

---

## 7. Рекомендация приёмке (Notion-агент)

Перезапустить независимо: `cargo test`, `cargo fmt --check`,
`cargo clippy --all-targets --all-features -- -D warnings`, `npm run check`,
`npm test`, весь Python-блок, `scripts/smoke_test.py --mode=cli`,
`scripts/check_real_sidecar_tests.py` в require-режиме с системным Python.
Ключевые тесты для точечной проверки:

```
cargo test --manifest-path desktop/localcomet-desktop/src-tauri/Cargo.toml --lib files::tests::long_path
cargo test --manifest-path desktop/localcomet-desktop/src-tauri/Cargo.toml --lib files::tests::short_alias
cargo test --manifest-path desktop/localcomet-desktop/src-tauri/Cargo.toml --lib control_plane::tests::model_turn_
```

Активацию инструментов по-прежнему **не подписывать**: этот патч закрывает
E1/E2/E6 и wire-binding `assistant_context`, но не заменяет свежий независимый
MVP-P0-C-A2 PASS.
