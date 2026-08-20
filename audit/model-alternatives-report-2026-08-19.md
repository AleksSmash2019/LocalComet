# Альтернатива Qwen2.5 1.5B для LocalComet

**Дата исследования:** 19 августа 2026 года  
**Задача:** найти более новую и эффективную модель примерно класса 1–2B параметров для русского локального чата, Computer Use и работы на широком диапазоне ПК.

## Краткий вывод

Наиболее перспективная **эффективная альтернатива** — **LiquidAI LFM2.5-1.2B-Instruct**. По опубликованным разработчиком результатам она превосходит Qwen3-1.7B в ряде instruction/reasoning/tool-use тестов и заметно меньше по опубликованному Q4_K_M-артефакту: около 731 MB против около 1.4 GB у Qwen3-1.7B. Однако есть критическое ограничение: официальная карточка LFM2.5 перечисляет только восемь языков — английский, арабский, китайский, французский, немецкий, японский, корейский и испанский — **русский не указан**. Кроме того, модель выпускается под собственной лицензией `lfm1.0`, а не Apache 2.0. Поэтому без локальной русской проверки и юридической проверки условий её нельзя назначать универсальным default LocalComet.

Для LocalComet наиболее безопасная практическая замена именно **русскоязычного baseline** — **Qwen3-1.7B-Instruct**. Это Apache 2.0, 1.7B dense, 32K контекст, заявленная поддержка 100+ языков с русским в официальном списке, встроенные thinking/non-thinking режимы, tool-use и прямая поддержка llama.cpp. Он будет тяжелее Qwen2.5 1.5B, но существенно новее и функционально сильнее. Моя рекомендация: **не удалять текущий Qwen2.5 1.5B; сначала добавить Qwen3-1.7B как основной русский/Computer Use кандидат, а LFM2.5-1.2B тестировать как отдельный “быстрый режим” только после проверки русского качества и лицензии.**

## Сравнение кандидатов

| Модель | Размер / формат | Русский | Tool/Computer Use сигнал | Опубликованный Q4_K_M | Лицензия | Итоговая роль |
|---|---:|---|---|---:|---|---|
| Qwen2.5-1.5B-Instruct | 1.54B; Q4_K_M | Да, 29+ языков | Хорошая база, но старее | ~986 MB | Apache 2.0 | Текущий безопасный fallback |
| **Qwen3-1.7B-Instruct** | 1.7B; Q4_K_M | **Да; 100+ языков, русский указан** | **Сильная официальная agent/tool-use позиция; llama.cpp** | ~1.4 GB | **Apache 2.0** | **Рекомендуемый русский default после локального smoke** |
| **LFM2.5-1.2B-Instruct** | 1.17B; Q4_K_M | **Русский не указан; 8 языков** | **Сильный agent/tool-use сигнал; llama.cpp** | **~731 MB** | `lfm1.0` | Быстрый режим после русской и лицензированной проверки |
| Granite-4.0-1B / H-1B | 1B dense / 1.5B hybrid; GGUF | Русский не указан; 12 языков | Сильное function calling/JSON | ~1.02 GB для 1B GGUF | Apache 2.0 | Дополнительный tool/JSON эксперимент |
| Gemma 3 1B IT | 1B | Более 140 языков заявлено для семейства | Не лучший подтверждённый выбор для текущего Computer Use | Требует проверки конкретного GGUF | Gemma Terms | Не универсальный default из-за условий использования |
| SmolLM2-1.7B-Instruct | 1.7B | **Англоязычный фокус** | Function calling поддерживается | Зависит от quant | Apache 2.0 | Английский/экспериментальный режим |
| Marco-Nano-Instruct | 8B total / 0.6B active MoE | Русский указан | Сильные vendor claims, но сложнее runtime | Не same-size dense | Apache 2.0 | R&D, не baseline для “любого ПК” |

## Почему LFM2.5 выглядит очень сильной

Liquid AI сообщает, что LFM2.5-1.2B-Instruct получил GPQA 38.89, MMLU-Pro 44.35, IFEval 86.23, IFBench 47.33, Multi-IF 60.98, AIME25 14.00 и BFCLv3 49.12. В той же таблице Qwen3-1.7B получил 34.85, 42.91, 73.68, 21.33, 56.48, 9.33 и 46.30 соответственно. Особенно заметна заявленная разница в instruction-following и IFBench.

Liquid AI также заявляет низкие требования к памяти и высокую скорость: на Snapdragon Gen4 CPU с llama.cpp Q4_0 — 70 decode tok/s и 719 MB для LFM2.5 против 40 tok/s и 1306 MB для Qwen3-1.7B. На Ryzen AI 9 HX 370 компания приводит для LFM2.5 116 decode tok/s, 856 MB и 2975 prefill tok/s. Это vendor-reported показатели на конкретных устройствах, поэтому они не заменяют измерение на пользовательском Windows ПК.

Главный недостаток для LocalComet — русский язык. Официальная HF-карточка LFM2.5 не обещает русский и прямо рекомендует модель для agentic tasks, extraction и RAG, но не рекомендует её для knowledge-intensive tasks и programming. Это делает её привлекательной для быстрого tool-router, но рискованной как единственную русскую разговорную модель.

## Почему Qwen3-1.7B — безопаснее как основной кандидат

Qwen3-1.7B имеет Apache 2.0, 32K контекст и официально поддерживает более 100 языков; русский включён в список Qwen3. Модель поддерживает non-thinking режим для быстрых ответов и thinking режим для сложных задач. Для non-thinking Qwen рекомендует Temperature 0.7, TopP 0.8, TopK 20 и MinP 0. Официальные материалы отдельно описывают agent capabilities, tool calling и локальный запуск через llama.cpp.

Цена этой надёжности — больший артефакт и расход памяти. По опубликованной Ollama-карточке Qwen3-1.7B Q4_K_M занимает около 1.4 GB против около 986 MB у текущего Qwen2.5-1.5B. Это всё ещё реалистичный размер для обычных ПК, но уже не такой универсальный, как Qwen2.5 1.5B.

## Что не следует делать сейчас

Не следует сразу менять default и удалять Qwen2.5 1.5B. Не следует считать vendor benchmarks доказательством русского качества или стабильности Computer Use. Также не следует выбирать Granite H-1B только из-за меньшего числа активных вычислений: гибридная Mamba-архитектура и предупреждения GGUF о precision errors требуют проверки именно текущей версии llama.cpp.

## Предлагаемый порядок локальной проверки

1. Оставить Qwen2.5 1.5B как fallback.
2. Добавить Qwen3-1.7B-Instruct Q4_K_M без удаления текущего артефакта.
3. Сравнить на одинаковых настройках: русский фактологический вопрос, английский вопрос, многоходовый контекст, короткий код, JSON, `Открой калькулятор`, `Открой блокнот`, повторный Computer Use, переход в новый чат и восстановление после timeout.
4. Отдельно измерить first-token latency, decode tok/s, пиковую память и стабильность после десяти последовательных turns.
5. После этого проверить LFM2.5-1.2B-Instruct Q4_K_M как быстрый кандидат, уделив особое внимание русскому, программированию и лицензии `lfm1.0`.
6. Только модель, которая проходит весь пользовательский smoke и не ухудшает Computer Use, можно назначать default.

## Рекомендация

**Для русскоязычного LocalComet сейчас рекомендую тестировать Qwen3-1.7B как основную замену Qwen2.5 1.5B, сохранив Qwen2.5 1.5B fallback.**

**Для режима “максимум скорости и минимум памяти” первым экспериментом рекомендую LFM2.5-1.2B-Instruct, но не как безусловную замену:** русский язык не заявлен, лицензия нестандартная, а сама карточка ограничивает область применения knowledge-heavy и programming задачами.

### References

[1]: https://qwenlm.github.io/blog/qwen3/ "Qwen3 official release blog"
[2]: https://huggingface.co/Qwen/Qwen3-1.7B "Qwen3-1.7B official model card"
[3]: https://www.liquid.ai/blog/introducing-lfm2-5-the-next-generation-of-on-device-ai "Liquid AI LFM2.5 official announcement"
[4]: https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct "LFM2.5-1.2B-Instruct official model card"
[5]: https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF "LFM2.5 official GGUF card"
[6]: https://docs.liquid.ai/lfm/models/complete-library "Liquid AI model library and formats"
[7]: https://huggingface.co/google/gemma-3-1b-it "Gemma 3 1B official model card"
[8]: https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct "SmolLM2 official model card"
[9]: https://huggingface.co/ibm-granite/granite-4.0-h-1b "Granite 4.0 H-1B official model card"
[10]: https://huggingface.co/ibm-granite/granite-4.0-1b-GGUF "Granite 4.0 1B official GGUF card"
[11]: https://huggingface.co/ATH-MaaS/Marco-Nano-Instruct "Marco-Nano-Instruct official model card"
[12]: https://ollama.com/library/qwen2.5:1.5b-instruct-q4_K_M "Qwen2.5 local artifact card"
[13]: https://ollama.com/library/qwen3:1.7b-q4_K_M "Qwen3 local artifact card"
