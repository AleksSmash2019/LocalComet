# LocalComet — Performance

## Baseline (2026-08-10)
| Метрика | Значение | Примечание |
|---------|----------|-----------|
| vitest | ~1.6 s | 390 тестов |
| svelte-check | 0 err/warn | — |
| cargo clippy | clean | `-D warnings` |
| MODEL_LOAD_TIMEOUT | 180 s | было 300 |
| Managed health poll | 3000 ms | было 2000 |
| Capability probe deadline | 2 s | было 5 |
| wait_bounded / join sleep | 200 ms / 20 ms | снижение CPU-spin |
| HTTP timeout (artifact download) | 60 s | предотвращает зависание |
| PROGRESS_UPDATE_BYTES | 128 KiB | плавность прогресс-бара |
| HF artifact-state polling | coalesced (500 ms) | устранение UI-jitter |

## Не измерено (нет bench-инфраструктуры — A-05)
- cold start desktop app
- время загрузки модели (стена)
- time to first token (TTFT)
- tokens per second
- RAM/VRAM под нагрузкой

## План (P2)
1. Bench-harness: `managed_runtime` start→ready latency, TTFT, tokens/s через фиксированный probe-промпт.
2. Логи `[PERF]` уже есть для `managed_artifact_trust_bundle` — расширить на load/generate.
3. Целевые пороги (Windows, mid-tier): cold start < 5 s, TTFT < 3 s после load, загрузка 7B Q4 < 60 s.

## Принципы
- Не блокировать UI длительными операциями (spawn_blocking в Rust, async в TS).
- Bounded buffers (≤4 MiB IPC), throttle progress events.
- Coalesce высокочастотные опросы состояния.
