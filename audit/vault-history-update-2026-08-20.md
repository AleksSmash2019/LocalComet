

## 2026-08-20 — verified LocalComet effort/thinking и local Vault boundary

Добавлена система effort/thinking с уровнями Off, Low, Medium и High, отдельным reasoning stream и сворачиваемым reasoning-блоком в чате. Qwen3-1.7B Q4_K_M назначена предпочтительной установленной моделью с fallback на Qwen2.5 1.5B. Финальный прогон LocalComet завершён с результатом **71/71 PASS**.

LocalComet workspace настроен на локальную папку `C:\Users\DNS\Documents\LocalCometVault`. Добавлен local-folder-only Markdown adapter с canonical-root confinement, SHA-256 optimistic concurrency, proposal/apply workflow и atomic UTF-8 writes. Реальный Vault проверен только read-only; найдено 435 Markdown-файлов. В этой сессии существующие заметки Vault не перезаписывались и не удалялись.

Связанная verified запись: [[10 Заметки сессий/2026-08-20 LocalComet effort-thinking и Vault]].
