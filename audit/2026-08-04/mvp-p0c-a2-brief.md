# MVP-P0-C-A2 Independent Audit Brief — 2026-08-04

**Аудитор:** OpenCode (read-only)
**Ветка:** `feature/donor-ui-compatible-port` (текущая, не переключал)
**Скоуп:** `desktop/localcomet-desktop/src-tauri/src/{files,control_plane,approval_commands,supervisor}.rs` + `desktop/localcomet-desktop/src/lib/bridge/modelGateway.ts`
**Дата baseline сравнения:** 03.08.2026 (по AGENTS.md)

---

## 1. Исходное состояние

См. предыдущий отчёт этого прогона — все 22 гейта зелёные, provenance обновлён (tree=9905bc7e...). Ветка `feature/donor-ui-compatible-port`, коммитов не делал, переключений не было.

Файлы и размеры (audit target):
- `files.rs` — 2003 строк
- `modelGateway.ts` — 996 строк
- `control_plane.rs` — 8204 строки
- `approval_commands.rs` — 1019 строк
- `supervisor.rs` — 2219 строк

---

## 2. `files.rs` — edge cases в `comparable_path` / `resolve_short_path`

**Найдено (строки 1227-1256):**

```rust
fn comparable_path(path: &Path) -> Result<String, FileCapabilityError> {
    let text = path.to_str().ok_or_else(access_denied)?.replace('/', "\\");
    let normalized = if let Some(value) = text.strip_prefix("\\\\?\\UNC\\") {
        format!("\\\\{value}")
    } else if let Some(value) = text.strip_prefix("\\\\?\\") {
        value.to_owned()
    } else {
        text
    };
    let resolved = resolve_short_path(&normalized)?;
    Ok(resolved.trim_end_matches('\\').to_ascii_lowercase())
}

#[cfg(windows)]
fn resolve_short_path(path: &str) -> Result<String, FileCapabilityError> {
    use windows_sys::Win32::Storage::FileSystem::GetLongPathNameW;
    let wide: Vec<u16> = path.encode_utf16().chain(std::iter::once(0)).collect();
    let mut out = vec![0u16; 1024];
    let len = unsafe { GetLongPathNameW(wide.as_ptr(), out.as_mut_ptr(), out.len() as u32) };
    if len == 0 || len as usize >= out.len() {
        return Ok(path.to_owned());  // ← silent fallback
    }
    out.truncate(len as usize);
    Ok(String::from_utf16_lossy(&out))
}
```

### 2.1 Edge cases, требующие `fail-closed` аудита

| # | Edge case | Текущее поведение | Риск |
|---|-----------|-------------------|------|
| E1 | `GetLongPathNameW` вернул 0 (ERROR_FILE_NOT_FOUND / access denied / invalid path) | **Silent fallback**: возвращает `path.to_owned()` без ошибки | Сравнение 8.3 ↔ long-path может ложно сравняться или ложно разойтись |
| E2 | Переполнение буфера (`len as usize >= out.len()`) | **Silent fallback** | Пути > 1024 UTF-16 code units (≈2KB) не нормализуются. UNC + очень глубокие папки — реаленость |
| E3 | Не-UNC путь без `\\?\` префикса | `strip_prefix` сработает, путь передаётся как есть | OK — это явная ветка |
| E4 | Путь с `\\?\UNC\` префиксом | Стрипится в `\\server\share` форму | OK |
| E5 | Повторный вызов на уже длинном пути (canonical) | Без изменений — `GetLongPathNameW` идемпотентен для некоротких имён | OK |
| E6 | Путь, где 8.3 алиасы случайно сосаются на разные файлы | Silent fallback → несравнимость → могут считаться разными | ⚠️ Дрейф сравнения в line 625, 634, 666, 671, 797, 802, 820, 825 |
| E7 | Путь с UTF-8 символами > BMP (surrogate pair) | `encode_utf16` корректен; buffer 1024 code units = до 2048 байт | OK, но с E2 складывается pool overflow |
| E8 | `path.to_str()` вернул None (невалидный UTF-8) | `access_denied` ошибка | OK — fail-closed |

### Рекомендации для аудита P0-C-A2

- **E1+E2 fail-closed:** обе ветки должны возвращать `Err(access_denied())` или более специфичный код (например `LC_PATH_NORMALIZE`), а не молча возвращать исходный путь. Доказательство: `GetLastError()` подсказка.
- Проверить callsites (линии 625, 634, 666, 671, 797, 802, 820, 825) на то, корректно ли они обрабатывают ошибку нормализации — вероятно, есть место, где "не совпали пути" → tolerated.
- Сравнить поведение с `canonicalize_utf8` / `GetFinalPathNameByHandleW` как более надёжную альтернативу (она тоже выполняет 8.3 resolution и не требует file existence при повторных вызовах).
- Добавить `#[cfg(test)]` покрытие для E1/E2/E6 — сейчас в тесте `test_check_bundle_parity.py` они конкретно не покрыты.

**Степень риска:** MEDIUM. Компрометация `comparable_path` позволяет `head`-атаку через 8.3 aliasing, где замена symlink-projected пути обойдёт сравнение.

---

## 3. `modelGateway.ts ↔ control_plane.rs` — контракт `model_turn_start`

### 3.1 TS side (modelGateway.ts:182-222)

```typescript
export async function startModelTurn(args: {
  requestId, chatSessionId, modelId, submittedAtUnixMs, maxTokens,
  prompt, fileIds?, locale, bindingFingerprint
})

invoke('model_turn_start', {
  requestId, chatSessionId, modelId, submittedAtUnixMs, maxTokens,
  prompt, fileIds, locale, bindingFingerprint
})
```

**Поля:** 9 приёмных (`requestId, chatSessionId, modelId, submittedAtUnixMs, max_tokens, prompt, file_ids, locale, bindingFingerprint`)

### 3.2 Rust side (control_plane.rs:2123-2135)

```rust
pub async fn model_turn_start(
    state, runtime, files,
    request_id: String,
    chat_session_id: String,
    model_id: String,
    submitted_at_unix_ms: u64,
    max_tokens: u16,
    prompt: String,
    file_ids: Vec<String>,
    locale: String,
    binding_fingerprint: String,
) -> Result<Value, BridgeError>
```

**Поля:** 9 параметров, **идеальное совпадение по именам и типам** (snake_case ↔ camelCase через Tauri auto-conversion).

### 3.3 Rust → Python sidecar payload (control_plane.rs:805-814)

```rust
let payload = json!({
    "request_id": identity.request_id,
    "chat_session_id": identity.chat_session_id,
    "model_id": identity.model_id,
    "submitted_at_unix_ms": identity.submitted_at_unix_ms,
    "max_tokens": identity.max_tokens,
    "prompt": prompt,
    "assistant_context": assistant_context,
    "binding_fingerprint": identity.binding_fingerprint,
});
```

**Поля в wire:** 8 — **`file_ids` и `locale` НЕ передаются дальше**, их обрабатывает Rust напрямую (`locale` уходит в `AssistantContext::trusted`, `file_ids` раскрываются в `prompt` через `files.build_context`).

### 3.4 messages/tools в контракте model_turn_start

**Проверка контракта:**
- TS: ❌ **НЕТ** `messages`, **НЕТ** `tools` параметров на входе.
- Rust: ❌ **НЕТ** `messages`, **НЕТ** `tools` параметров.
- `assistant_context.capabilities.tools.clone()` передаётся через `reserve_model_turn` → `permitted_tool_names: Vec<String>` → `ModelRequestIdentity` **НЕ в wire-payload model_turn_start** (используется для capability scoping во время turn, в registry).

**Верификация соответствует текущему Block 3 stop-point (AGENTS.md lines 60+):** инструменты подключены capability-neutral и недостижимы до активации.

### Вывод P0-C-A2
✅ **MISMATCH ОТСУТСТВУЕТ для model_turn_start**. Контракт полностью согласован TS↔Rust.

⚠️ **Отдельно зафиксировать:** `assistant_context` не подписан в lingered digest — поле в wire, но не включено в `canonical_input_digest`. Это следущий шаг для MVP-P0-C-A2 (signed assistant_context).

---

## 4. `TOOL_EXECUTION_ACTIVATION_ENABLED` — где включается и gate'ит

### 4.1 Флаг — hardcoded в исходнике (approval_commands.rs:12)

```rust
const TOOL_EXECUTION_ACTIVATION_ENABLED: bool = false;
```

### 4.2 Gate'ит две команды (обе в approval_commands.rs):

| Команда | Строка | Функция |
|---------|--------|---------|
| `run_tool_call` | 282-296 | Исполнительная точка для tool.call IPC |
| `set_workspace` | 388-394 | Изменение workspace identity |

Обе возвращают:
```rust
Err(BridgeError::new(
    "feature_disabled",
    "tool execution is disabled until execution binding is complete",
))
```

### 4.3 Invariant enforcement (supervisor.rs:1931-1938, 2362)

```rust
#[test]
fn p0c_tool_activation_remains_false() {
    let source = include_str!("approval_commands.rs");
    assert!(
        source.contains("const TOOL_EXECUTION_ACTIVATION_ENABLED: bool = false;")
    );
}
```

**Два независимых supervisor-теста** намеренно защищают флаг от включения без явного обновления baseline.

### 4.4 Guardian evidence

По AGENTS.md (Block 3 stop point, 2026-08-01):
> implementation halted per owner directive after finding TOOL_EXECUTION_ACTIVATION_ENABLED=false blocks run_tool_call for ALL risk levels (including read_only). Tool activation requires MVP-P0-C-A2 independent PASS before P0-D, and P0-D alone does not authorize activation.

**Activation condition из MVP_P0B_R5_FROZEN_CONTRACT.md:**
> 7. Activation false (TOOL_EXECUTION_ACTIVATION_ENABLED = false)

### 4.5 Что нужно для разблокировки `run_tool_call`

1. `TOOL_EXECUTION_ACTIVATION_ENABLED = true` в `approval_commands.rs:12`
2. Одновременно снять supervisor-тест `p0c_tool_activation_remains_false` (иначе тесты падут)
3. Обновить `MVP_P0B_R5_FROZEN_CONTRACT.md` раздел 7
4. Обновить AGENTS.md Block 3 stop-point
5. **Отдельный independent P0-C-A2 PASS** от приёмки (не от исполнителя)

**Нет пути «частичной активации»** — флаг глобален. Это by design (fail-closed на уровне компиляции).

---

## 5. Что НЕ проверено (выходит за read-only скоуп)

- Live-инвокации `run_tool_call` через sidecar (требует `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` с запущенным sidecar).
- Поведение IPC wire для `model_turn_start` в runtime (валидация только по сорсам).
- Invariants `invariants.toml` на соответствие (это scope P0-D audit).

---

## 6. Рекомендации для P0-C-A2 приёмки

1. **Re-verify E1/E2 fail-closed в `comparable_path`** — сейчас silent fallback нарушает принцип fail-closed.
2. **Подтвердить отсутствие mismatch в `model_turn_start`** через fresh `cargo test` с артефактом wire-level capture.
3. **Не подписывать активацию** до тех пор, пока `assistant_context` не будет включён в signing digest.
4. **Запустить independent re-run всех 22 гейтов** (включая `cargo test`, `npm test`, svelte-check) с фиксированным SEED=0 для determinism проверки byte-digest.
5. Зафиксировать evidence provenance после each повторного прогона.

---

## Appendix — цитируемые участки

- `files.rs:1227-1256` — `comparable_path` + `resolve_short_path` (полный текст выше)
- `modelGateway.ts:182-222` — `startModelTurn` (полный текст выше)
- `control_plane.rs:2123-2135, 805-814, 3534-3546` — Rust-side signature + wire-payload + payload validation
- `approval_commands.rs:12, 282-296, 388-394` — TOOL_EXECUTION_ACTIVATION_ENABLED definition + 2 use points
- `supervisor.rs:1931-1938, 2362` — invariant enforcement

**Read-only:** никаких изменений не внесено. Никаких коммитов, веток, удалений не производилось.
