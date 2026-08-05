# ЧАСТЬ B — Hugging Face интеграция: дизайн и план миграции модели

**Статус документа:** design only. **Ни одного изменения в production-файлах не
внесено** — ни в `approved-artifacts.v1.json`, ни в `artifact_acquisition.rs`,
ни в `artifact_trust.rs`. Все хеши, размеры и ревизии ниже — **placeholder-ы**
вида `<...>`; их запрещено заполнять по памяти или по метаданным HF-страницы,
только из фактически скачанных байтов (evidence class A: байты на диске + SHA-256).

**Дата:** 2026-08-04 · **Ветка:** `feature/donor-ui-compatible-port` (не переключалась)
**Изученные источники:**
`desktop/localcomet-desktop/src-tauri/src/artifact_acquisition.rs` (2296 строк),
`desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs` (3557 строк),
`desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json`,
`desktop/localcomet-desktop/src-tauri/src/managed_runtime.rs`.

---

## 1. Что фактически есть сегодня

### 1.1 Каталог — embedded, hash-pinned, canonical (INV-CATALOG-001)

```rust
// artifact_trust.rs:33-35
const CATALOG_BYTES: &[u8] = include_bytes!("../resources/localcomet/approved-artifacts.v1.json");
const EMBEDDED_CATALOG_SHA256: &str =
    "29bbbe33c207417415f637bafc4dc3853c04cf68db05d9be2a6e661c5f93c605";
```

`canonical_catalog_bytes` (artifact_trust.rs:1286) сначала нормализует переводы
строк (`\r\n` → `\n`, одиночный `\r` → `invalid_catalog`), затем сверяет SHA-256
с константой. Любая правка JSON без обновления константы = `invalid_catalog`
на старте, то есть каталог **не переопределяется ни файлом на диске, ни app-data**.
Каталог — единственный источник артефактной истины; AppData не является авторитетом
(`live_inventory_revalidates_exact_bytes_and_ignores_appdata_authority`).

### 1.2 Единственная модель в каталоге

```
model_id            qwen2.5-1.5b-instruct-q4-k-m
upstream_repository Qwen/Qwen2.5-1.5B-Instruct-GGUF
upstream_revision   91cad51170dc346986eccefdc2dd33a9da36ead9   (pinned commit)
asset_filename      qwen2.5-1.5b-instruct-q4_k_m.gguf
asset_bytes         1 117 320 736
asset_sha256        6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
license_id          Apache-2.0
compatible_runtime  llama-cpp-windows-x86-64-cpu-bootstrap
status              approved_internal_bootstrap
bootstrap_purpose   INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION
primary_url         https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/
                    91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf
allowed_redirect_hosts
                    cas-bridge.xethub.hf.co, cdn-lfs-us-1.hf.co, cdn-lfs.hf.co,
                    huggingface.co, transfer.xethub.hf.co, us.aws.cdn.hf.co
```

### 1.3 Schema-инварианты для модели (`artifact_trust.rs:1643-1719`)

Жёсткие, отказ = `invalid_catalog`:

| Поле | Требование |
|---|---|
| `model_id` | 3..96 символов, только `[a-z0-9._-]`, первый — буква/цифра, уникален среди всех артефактов |
| `format` | ровно `"GGUF"` |
| `quantization` | ровно `"Q4_K_M"` (**захардкожено**) |
| `asset_bytes` | > 0 и ≤ 128 GiB |
| `asset_sha256` | 64 hex lowercase |
| `asset_filename` | валидное имя, оканчивается на `.gguf`, уникально в каталоге |
| `managed_relative_path` | относительный Windows-путь; его последний сегмент **равен** `asset_filename`; не пересекается с другими managed-путями |
| `public_distribution`, `installer_bundled` | обязательно `false` |
| `bootstrap_purpose` | ровно `INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION` |
| `status` | единственный вариант `CatalogStatus::ApprovedInternalBootstrap` |
| `compatible_runtime_ids` | непусто, sorted+unique, каждый id существует в `runtimes` |
| `provider/family/display_name/upstream_repository/upstream_revision/license_id` | непустой текст ≤ 256 байт, без control-символов |
| всего артефактов | ≤ `MAX_ARTIFACTS = 32` |

### 1.4 Инварианты acquisition (`artifact_trust.rs:1736-1808`)

| Поле | Требование |
|---|---|
| `source_type` | ровно `approved_https` (`AcquisitionSourceType::ApprovedHttps`) |
| `artifact_id` / `artifact_kind` | точно совпадают с моделью / `model` |
| `expected_filename` / `expected_bytes` / `expected_sha256` / `managed_relative_destination` | **точно равны** соответствующим полям модели (дублирование по значению, а не по ссылке) |
| `automatic_download` | `false` |
| `user_confirmation_required` | `true` |
| `public_distribution`, `installer_bundled` | `false` |
| `primary_url` | `https://`, ≤ 2048 символов, без `? # @ \` и control-символов, обязательный path; host обязан присутствовать в `allowed_redirect_hosts`; URL уникален по всему каталогу |
| `allowed_redirect_hosts` | 1..16 записей, отсортированы, без дублей, каждый host — lowercase `[a-z0-9.-]`, содержит точку, не начинается/не заканчивается точкой, ≤ 253 байт |
| `content_type` | опционально, ≤ 128 символов, ограниченный алфавит |

### 1.5 Инварианты загрузки (`artifact_acquisition.rs`)

- `Policy::none()` (artifact_acquisition.rs:927) — реqwest **не** следует
  редиректам сам. Цикл ручной: `for _ in 0..=MAX_REDIRECTS (5)`, на каждом шаге
  `validate_redirect_url(&url, allowed_hosts)` — https + **точное** совпадение
  хоста со списком (без wildcard, без суффиксного матчинга;
  `model_redirect_authority_requires_exact_https_host` это фиксирует).
  Превышение лимита → `redirect_limit_exceeded`.
- `validate_content_type` (artifact_acquisition.rs:976) — сверка с `content_type`
  из каталога.
- Стриминг в `*.partial` с точным контролем размера: `received > expected` →
  немедленный `size_mismatch`; недобор ловится при последующей верификации.
- SHA-256 всего файла перед промоушеном: `sha256_file(&partial) != expected_sha256(artifact)`
  → отказ (artifact_acquisition.rs:467).
- Для моделей — проверка magic bytes GGUF (artifact_acquisition.rs:1010-1014) до
  установки (`model_validation_rejects_bad_gguf_magic_before_installation`).
- `DISK_RESERVE_BYTES = 64 MiB` запаса, атомарный промоушен, cancel-safe очистка
  только собственных partial-файлов, validation-cache с инвалидацией по
  catalog digest.

### 1.6 Рантайм

`llama-cpp-windows-x86-64-cpu-bootstrap` (llama.cpp b10068, CPU-only, MIT,
loopback-only, `openai-compatible-v1`), фиксированные аргументы
(`managed_runtime.rs:1203-1222`):

```
--model <path> --host 127.0.0.1 --port <port> --api-key-file <file>
--no-webui --no-agent --ctx-size 4096 --n-predict 512 --alias <alias>
```

Список флагов дополнительно валидируется через capability-probe
(`REQUIRED_FLAGS`, `--version`/`--help`).

---

## 2. Дизайн: как добавить модель из Hugging Face в approved-каталог

### 2.1 Инварианты, которые дизайн обязан сохранить

1. **Только `approved_https`.** Никакого HF-API, `hf_hub_download`, токенов,
   поиска по репозиториям, «latest»-тегов. Только один заранее подписанный
   `primary_url` с **pinned commit revision** в пути `/resolve/<sha>/<file>`
   (не `/resolve/main/`: `main` — мутабельная ссылка и класс D/E-доказательство).
2. **Только модели из pinned-каталога.** Ни UI, ни сайдкар, ни LLM не могут
   предложить model_id, которого нет в embedded-каталоге: `resolve_launch` /
   `model_readiness` работают строго по каталогу, а сам каталог pinned по SHA-256.
3. **SHA-256 обязателен и проверяется по байтам** до промоушена; `expected_bytes`
   дублирует размер и режет overshoot ещё в потоке.
4. **`allowed_redirect_hosts` — только HF CDN.** Разрешается **только** уже
   зафиксированное множество hf-хостов (см. §1.2). Новый хост добавляется
   исключительно после наблюдения реального `Location` в трейсе загрузки
   (evidence class A), никогда «на всякий случай». Wildcard невозможен
   архитектурно — сравнение точное.

### 2.2 Процедура добавления модели (7 шагов)

**Шаг 1. Выбрать и заморозить upstream.**
Определить `repo` (например `Qwen/Qwen2.5-7B-Instruct-GGUF`), файл нужной
квантизации (`*-q4_k_m.gguf`) и **commit sha** репозитория. Ревизия должна быть
полным 40-hex sha, а не тегом.

**Шаг 2. Скачать вне продукта и снять доказательства.**
Скачивание выполняет человек/CI, не агент. Зафиксировать:
`asset_bytes` (реальный размер файла), `asset_sha256` (SHA-256 байтов на диске),
первые 4 байта = `GGUF`, и **цепочку редиректов** (все `Location`-хосты)
— именно из неё берётся `allowed_redirect_hosts`.

**Шаг 3. Проверить лицензию по байтам.**
`license_id` — не декоративное поле. Для семейства Qwen2.5 лицензии по размерам
**различаются** (часть моделей Apache-2.0, часть — под Qwen Research/Community
лицензией с ограничениями). Это обязательный check-item: прочитать файл лицензии
в самом upstream-репозитории на pinned-ревизии и вписать его SPDX-идентификатор.
До этой проверки любое значение `license_id` — класс C (intent), не A.
Для рантайма уже существует прецедент строгой привязки текста лицензии
(`license_asset` + `sha256`, `LLAMA_CPP_LICENSE_BYTES`); для моделей текст
лицензии сейчас не пинуется — если владелец захочет тот же уровень, это отдельная
схема-правка (новое поле + bump `schema_version`), в этот скоуп она не входит.

**Шаг 4. Собрать запись каталога.**

```jsonc
{
  "model_id": "qwen2.5-7b-instruct-q4-k-m",
  "provider": "Qwen",
  "family": "Qwen2.5",
  "display_name": "Qwen2.5 7B Instruct Q4_K_M",
  "format": "GGUF",
  "quantization": "Q4_K_M",
  "upstream_repository": "Qwen/Qwen2.5-7B-Instruct-GGUF",
  "upstream_revision": "<40-hex commit sha>",
  "asset_filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
  "asset_bytes": <точный размер в байтах>,
  "asset_sha256": "<64 hex lowercase>",
  "acquisition": {
    "artifact_id": "qwen2.5-7b-instruct-q4-k-m",
    "artifact_kind": "model",
    "source_type": "approved_https",
    "primary_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/<sha>/qwen2.5-7b-instruct-q4_k_m.gguf",
    "allowed_redirect_hosts": ["cas-bridge.xethub.hf.co", "cdn-lfs-us-1.hf.co",
                               "cdn-lfs.hf.co", "huggingface.co",
                               "transfer.xethub.hf.co", "us.aws.cdn.hf.co"],
    "expected_filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
    "expected_bytes": <тот же размер>,
    "expected_sha256": "<тот же sha>",
    "content_type": "application/octet-stream",
    "managed_relative_destination": "qwen2.5-7b-instruct-q4-k-m/qwen2.5-7b-instruct-q4_k_m.gguf",
    "public_distribution": false,
    "installer_bundled": false,
    "automatic_download": false,
    "user_confirmation_required": true
  },
  "license_id": "<SPDX из шага 3>",
  "compatible_runtime_ids": ["llama-cpp-windows-x86-64-cpu-bootstrap"],
  "managed_relative_path": "qwen2.5-7b-instruct-q4-k-m/qwen2.5-7b-instruct-q4_k_m.gguf",
  "public_distribution": false,
  "installer_bundled": false,
  "bootstrap_purpose": "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION",
  "status": "approved_internal_bootstrap"
}
```

Формат файла: одна строка JSON, ключи в том же порядке, что у существующей
записи (файл сейчас — однострочный minified JSON; порядок ключей влияет на
байты, а байты влияют на pin).

**Шаг 5. Обновить pin.**
`EMBEDDED_CATALOG_SHA256` = SHA-256 нормализованных (LF) байтов нового JSON.
Считать по факту (`Get-FileHash`/`sha256_bytes`), не «дописывать по смыслу».
Тесты `embedded_catalog_is_canonical_and_exactly_pinned` и
`synthetic_lf_and_crlf_catalogs_normalize_to_the_same_pinned_bytes` — приёмочный
критерий этого шага.

**Шаг 6. Обновить зависимые ассерты.**
Каталожная идентичность продублирована в тестах (это by design — они фиксируют
инвариант, а не читают его):
`artifact_trust.rs:2859-2876` (поля модели, primary_url),
`artifact_trust.rs:3504-3550` (`model_readiness`/`resolve_launch`),
`artifact_acquisition.rs:1617` (redirect-authority),
`control_plane.rs` (7 мест с `model_id: "qwen2.5-1.5b-instruct-q4-k-m"`),
frontend-тесты `managed-artifacts.test.ts`, `chat-reliability.test.ts`,
`assistant-usability.test.ts`, `p0b-r5-approval-contract.test.ts`.
Python-сайдкар model_id **не** знает (провайдер-агностичен) — правок в
`modules/`/`core/`/`agents/` не требуется, что подтверждается тем, что
`git grep qwen2.5-1.5b` по этим каталогам пуст.

**Шаг 7. Прогнать полный набор гейтов из AGENTS.md** плюс живой acceptance:
скачивание через продуктовый путь (approval → download → SHA-256 → GGUF magic →
атомарный промоушен), затем `resolve_launch` и реальный inference-turn.

### 2.3 Что дизайн сознательно НЕ вводит

- Никакой HF search/list API, никакого HF-токена и приватных репозиториев.
- Никакого «добавления модели из UI»: каталог embedded и pinned, добавление —
  это сборка нового бинарника, а не runtime-операция. Это и есть trust chain.
- Никакого нового `source_type` и никакого ослабления `validate_redirect_url`.
- Никакого авто-скачивания: `automatic_download: false`,
  `user_confirmation_required: true` — approval остаётся у человека.

---

## 3. План миграции Qwen2.5-1.5B → более крупная модель

### 3.1 Выбор цели

| Кандидат | Плюсы | Риски / блокеры |
|---|---|---|
| **Qwen2.5-7B-Instruct Q4_K_M** (рекомендуется) | тот же runtime и тот же формат; заметный прирост качества; официальный GGUF-репозиторий Qwen | ~4.5–5 GB на диск и в RAM при `--ctx-size 4096` → нужен ре-тест таймингов загрузки на целевой машине; лицензию подтвердить по байтам |
| Qwen2.5-3B-Instruct Q4_K_M | компромисс по RAM | **лицензия семейства 3B отличается от Apache-2.0** (Qwen Research/Community) — до подтверждения по байтам это блокер, а не деталь |
| любая не-Q4_K_M квантизация | — | блокируется схемой: `quantization != "Q4_K_M"` → `invalid_catalog`. Потребовало бы правки allow-list квантизаций в `artifact_trust.rs` + отдельного аудита |

Вывод: миграция на **7B Q4_K_M** не требует изменений кода вообще — только данные
каталога, pin и ассерты. Миграция на другую квантизацию или на не-GGUF формат
требует правки схемы и отдельного разрешения.

### 3.2 Стратегия сосуществования: сначала добавить, потом убрать

Каталог поддерживает до 32 артефактов, а `MAX_MODEL_BYTES` = 128 GiB, поэтому
корректный порядок — **не замена, а добавление**:

- **Фаза 1 (add).** Новая модель добавляется рядом с 1.5B. Обе валидны, обе
  pinned. `compatible_runtime_ids` у обеих — существующий bootstrap-рантайм.
  managed-пути disjoint (разные подпапки по `model_id`), имена файлов уникальны,
  primary_url уникальны — все four uniqueness-проверки схемы соблюдены
  автоматически.
- **Фаза 2 (validate).** Живой acceptance на новой модели: download →
  hash → GGUF magic → промоушен → `model_readiness` → `resolve_launch` →
  реальный turn через `model.turn.start`. 1.5B в это время остаётся рабочим
  fallback-ом (никакого «сломали и починим потом»).
- **Фаза 3 (retire, только с явного разрешения владельца).** Удаление записи
  1.5B из каталога = отдельный шаг с новым pin и обновлением тестов. Файлы
  на диске в `%LOCALAPPDATA%\LocalComet\...` **не удаляются** агентом (запрет
  AGENTS.md на удаление файлов). До Фазы 3 bootstrap-модель по умолчанию можно
  оставить прежней.

### 3.3 Пошаговый чек-лист миграции

1. `git status` — чистое исходное состояние, ветка `feature/donor-ui-compatible-port`.
2. Скачать 7B Q4_K_M вне продукта; снять `asset_bytes`, `asset_sha256`,
   GGUF magic, трассу редиректов; подтвердить SPDX-лицензию по байтам upstream.
3. Сверить трассу редиректов с текущим списком hf-хостов. Совпало — список не
   менять. Появился новый хост — добавить **только** его, сохранив сортировку и
   лимит 16, и приложить наблюдение как evidence.
4. Добавить запись модели в `approved-artifacts.v1.json` (порядок ключей как у
   существующей записи, одна строка, UTF-8 без BOM, LF).
5. Пересчитать и обновить `EMBEDDED_CATALOG_SHA256`.
6. Обновить ассерты в `artifact_trust.rs`, `artifact_acquisition.rs`,
   `control_plane.rs` и во frontend-тестах (список — §2.6 шага 6).
7. Гейты: `cargo test`, `cargo fmt --check`,
   `cargo clippy --all-targets --all-features -- -D warnings`, `npm run check`,
   `npm test`, весь Python-блок, `scripts/smoke_test.py --mode=cli`,
   `scripts/check_real_sidecar_tests.py` (require-режим),
   `scripts/refresh_evidence.py`, `scripts/check_evidence_provenance.py`.
8. Живой acceptance (Фаза 2) с записью реальных байтов/хешей/таймингов в
   evidence, включая время загрузки модели относительно
   `model_load_deadline` (`managed_runtime.rs`) — для 7B оно должно быть
   перепроверено, а не предположено.
9. Обновить baseline в `AGENTS.md` (числа тестов/артефактов) и приложить отчёт
   по формату из AGENTS.md.

### 3.4 Точки, где trust chain может сломаться (и почему предложенный порядок её сохраняет)

| Риск | Механизм защиты, который остаётся включённым |
|---|---|
| Подмена файла на CDN | `expected_sha256` по байтам + GGUF magic + `expected_bytes` |
| Ротация HF CDN → редирект на чужой хост | точное сравнение хоста, `Policy::none()`, лимит 5 редиректов |
| Мутабельная ревизия (`/resolve/main/`) | требование pinned 40-hex sha в `primary_url` |
| Правка каталога на диске / в AppData | `EMBEDDED_CATALOG_SHA256` + `include_bytes!` + отсутствие AppData-авторитета |
| «Модель есть в папке, значит валидна» | live-инвентарь ревалидирует байты; наличие файла не является доказательством |
| Тихая деградация квантизации/формата | хардкод `GGUF` + `Q4_K_M` в схеме |
| Обход approval | `automatic_download: false`, `user_confirmation_required: true` |

### 3.5 Что миграция НЕ должна затрагивать

`TOOL_EXECUTION_ACTIVATION_ENABLED` (остаётся `false`), `approval_commands.rs`,
orchestration/ApprovalCard/live tool execution, `bridge.py`,
`notion-bridge.mjs`, Vault, Projects, BrowserProfile. Смена модели — это
артефактный, а не capability-скоуп; она не является и не может считаться
основанием для активации инструментов.

---

## 4. Открытые вопросы к владельцу

1. Целевая модель: 7B Q4_K_M (Apache-2.0 ожидается, требует проверки) или 3B
   (лицензионный блокер)? RAM-бюджет целевой машины при `--ctx-size 4096`?
2. Оставлять ли 1.5B в каталоге как fallback (Фаза 1+2 без Фазы 3)?
3. Пинить ли текст лицензии модели по SHA-256, как это сделано для рантайма
   (это правка схемы и `schema_version`)?
4. Кто выполняет шаг 2 (скачивание и снятие хешей) — человек или CI? Агент этого
   делать не должен: результат должен быть независимо воспроизводим.
