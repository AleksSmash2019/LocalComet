# Перепроверка приложенного отчёта — 2026-08-20

## Фактическое состояние

Проверка выполнена в `C:\Users\DNS\Documents\LocalComet-build-week-clean`. Текущая ветка: `feat/up00-wp01-windows-one-click-launch`. HEAD: `a798bca`. `git status --short` содержит 372 записи, поэтому рабочее дерево действительно не чистое. Это совпадает с приложенным отчётом по ветке, HEAD и количеству записей.

Источник `modules/local_model_gateway_ru.py` в текущем рабочем дереве имеет SHA-256 `490E368B4BAB8DDCCB350969149675857A9519286179A5D0FDCCD83E7489281F`.

## Повторенные gates

`python tests/test_check_bundle_parity.py` повторён непосредственно на текущем дереве и завершился успешно: 2 теста, `OK`, exit 0. Поэтому утверждение приложения о текущем провале bundle parity не воспроизводится на момент перепроверки; ранее оно могло относиться к другому рабочему состоянию или содержать устаревший вывод.

`python scripts/check_evidence_provenance.py` повторён и завершился exit 1. Он повторно сообщает 4 stale evidence-файла с несовпадающим `tree_digest`: `cargo_test.txt`, `trust_chain.txt`, `cmd_parity.txt`, `tool_risk_registry.txt`. Это утверждение приложения подтверждено.

## Вывод

Приложенный отчёт частично актуален: branch/HEAD/грязное дерево и stale evidence подтверждаются; bundle parity сейчас проходит. Следующий безопасный шаг — после завершения согласованных исходных правок запустить `scripts/refresh_evidence.py`, затем повторить provenance gate. Файлы и мусор из отчёта не удалялись.
