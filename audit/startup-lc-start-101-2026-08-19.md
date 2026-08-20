# LC_START_101 startup investigation — 2026-08-19

## Исходное состояние

При пользовательском запуске установленного LocalComet отображалась ошибка `LC_START_101`, фаза `packaged backend start`. В момент воспроизведения dev-окружение LocalComet уже занимало локальные порты: Python sidecar слушал `127.0.0.1:8787`, а Vite dev server — `127.0.0.1:1420`. Штатный launcher doctor подтвердил `dev_port: 127.0.0.1:1420 is unavailable` и остановил новый dev launch с verdict `HOLD`.

Установленная версия была обнаружена по пути `C:\Users\DNS\AppData\Local\Programs\LocalComet\LocalComet.exe`; packaged backend — `localcomet-core.exe`. `startup.log` фиксировал старое событие `phase=backend_start status=failure.sidecar_unavailable code=LC_START_101`.

## Диагностика

Packaged sidecar runner и embedded Python backend были проверены напрямую в безопасном режиме с пустым stdin: runner вернул `exit=0` и отправил корректный `py-hello-000001` IPC hello, поэтому повреждения файлов sidecar или Python runtime не обнаружено. Коррелированный фактором была занятость dev-портов и оставшиеся dev launcher processes после пользовательского/аудитного запуска.

## Исправление и проверка

LocalComet desktop process был закрыт через `CloseMainWindow`. Для оставшихся Vite/sidecar launcher processes использован штатный `CTRL_BREAK_EVENT` через отдельный helper `audit/graceful_ctrl_break_detached.py`, без `Stop-Process`, `taskkill` или принудительного убийства. После этого порты `8787`, `1420` и `9223` были свободны.

Установленный `LocalComet.exe` был запущен повторно. В 21:24 packaged process `LocalComet` и `localcomet-core` оставались запущенными, а новая запись `startup.log` завершилась `phase=window_display status=success code=LC_START_200`; нового `LC_START_101` не появилось. Вывод: в данном воспроизведении LC_START_101 был вызван конфликтом оставшихся dev sidecar/Vite ports, а не повреждением packaged backend.

## Ограничение

Если dev-окружение оставляет порты 8787/1420 занятыми, установленный packaged LocalComet не может поднять собственный backend и сообщает LC_START_101. Перед packaged запуском необходимо штатно закрывать dev LocalComet/launcher или использовать раздельный профиль портов.
