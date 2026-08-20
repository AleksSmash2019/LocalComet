# Исследование альтернатив Qwen2.5 1.5B

Дата проверки: 2026-08-19. Цель: найти более новую и эффективную модель примерно класса 1–2B для LocalComet (llama.cpp/GGUF, русский чат, Computer Use/tool routing, работа на широком диапазоне ПК).

## Ключевые первичные источники

1. Qwen3 official release: https://qwenlm.github.io/blog/qwen3/
2. Qwen3-1.7B model card: https://huggingface.co/Qwen/Qwen3-1.7B
3. Gemma 3 official model card: https://huggingface.co/google/gemma-3-1b-it
4. SmolLM2-1.7B-Instruct model card: https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct
5. Liquid AI LFM2.5 announcement: https://www.liquid.ai/blog/introducing-lfm2-5-the-next-generation-of-on-device-ai
6. Liquid AI complete model library: https://docs.liquid.ai/lfm/models/complete-library
7. Marco-Nano-Instruct model card: https://huggingface.co/ATH-MaaS/Marco-Nano-Instruct

## Зафиксированные факты из первичных источников

### LFM2.5-1.2B-Instruct

Liquid AI называет LFM2.5-1.2B-Instruct общим instruction-tuned вариантом для большинства задач; заявлены SFT, preference alignment и multi-stage RL, включая instruction following и tool use. Компания позиционирует семейство как on-device и edge-oriented. Для text benchmarks в официальной публикации приведены: GPQA 38.89, MMLU-Pro 44.35, IFEval 86.23, IFBench 47.33, Multi-IF 60.98, AIME25 14.00 и BFCLv3 49.12. В той же таблице для Qwen3-1.7B указаны GPQA 34.85, MMLU-Pro 42.91, IFEval 73.68, IFBench 21.33, Multi-IF 56.48, AIME25 9.33 и BFCLv3 46.30. Эти значения являются vendor-reported и требуют локальной верификации одинаковым harness.

Официальные speed/memory claims Liquid AI: на Ryzen AI 9 HX 370, llama.cpp Q4_0, LFM2.5-1.2B-Instruct — 2975 prefill tok/s, 116 decode tok/s, 856MB; Qwen3-1.7B — 2008 prefill tok/s, 62 decode tok/s, 1465MB. На Snapdragon 8 Gen 4 CPU LFM2.5 — 335/70 tok/s и 719MB против Qwen3-1.7B — 181/40 tok/s и 1306MB. Это не прямой прогноз для Windows PC пользователя, но сильный сигнал в пользу отдельного on-device benchmark.

Liquid docs подтверждают наличие LFM2.5-1.2B-Instruct в HF, GGUF, MLX и ONNX, а также 32K context и поддержку llama.cpp, Ollama, vLLM, SGLang и Transformers. В документации Q4_K_M описан как баланс размера и качества. Official release также перечисляет LFM2.5-1.2B-Thinking, но для baseline LocalComet нужен Instruct; Thinking следует тестировать отдельно, так как latency и стабильность tool routing могут отличаться.

Официальная карточка LFM2.5-1.2B-Instruct уточняет, что репозитории используют собственную `lfm1.0` license, а не Apache/MIT. Для text Instruct явно перечислены только 8 языков: English, Arabic, Chinese, French, German, Japanese, Korean, Spanish; русского в списке нет. Карточка также прямо говорит, что модель рекомендуется для agentic tasks, extraction и RAG, но не рекомендуется для knowledge-intensive tasks и programming. Поэтому LFM2.5 — сильный кандидат на скорость/agentic efficiency, но не безопасный русский-first default без локального smoke/eval и отдельной проверки возможности распространения по условиям `lfm1.0`.

### Qwen3-1.7B

Qwen3-1.7B — dense 1.7B, Apache 2.0, 32,768 context, 28 layers, GQA 16 Q / 8 KV. Official Qwen materials state support for 100+ languages/dialects; official blog lists Russian. Qwen3 supports hybrid thinking and non-thinking modes; for non-thinking official recommendations are Temperature 0.7, TopP 0.8, TopK 20, MinP 0. Qwen3 official materials explicitly describe agent/tool use and local llama.cpp support. HF card warns about repetitions and recommends presence_penalty up to 1.5 when needed.

Qwen3-1.7B is the strongest low-risk compatibility candidate for LocalComet because the current app already uses Qwen family conventions and the license/tool/local-runtime story is clear. It is newer than Qwen2.5 1.5B but is not necessarily the absolute fastest or smallest.

### Gemma 3 1B IT

Gemma 3 1B IT is a 1B instruction model with Gemma terms/license rather than Apache 2.0. Google/HF model card states over 140 languages, but the 1B variant has 32K context while 4B/12B/27B have 128K. The card also describes multimodal Gemma 3 family, though the 1B text model's practical multimodal behavior must be separately verified. HF access requires acceptance of Google's usage conditions. It is a plausible quality candidate, but licensing/redistribution and Russian/tool-call behavior make it less attractive as LocalComet's universal default than Apache-licensed alternatives.

### SmolLM2-1.7B-Instruct

SmolLM2-1.7B-Instruct is Apache 2.0 and explicitly on-device oriented. The card states strong English-centric instruction following and function calling. Reported instruct scores: IFEval 56.7, MT-Bench 6.13, HellaSwag 66.1, MMLU-Pro 19.3, BBH 32.2 and GSM8K 48.2. The same card reports Qwen2.5-1.5B-Instruct at IFEval 47.4, MT-Bench 6.52, HellaSwag 60.9, MMLU-Pro 24.2, BBH 35.3 and GSM8K 42.8. The card explicitly says SmolLM2 primarily understands and generates English. Therefore it is not a strong Russian-first replacement despite good compact English performance.

### Granite 4.0 1B / H-1B

IBM Granite 4.0 Nano adds a newer Apache 2.0 candidate. The official H-1B card lists 1.5B parameters for the hybrid H variant and 1B for the traditional variant, with 32K/128K context depending on variant; the H-1B card lists Apache 2.0, function calling, structured output, RAG and on-device use. The official language list is English, German, Spanish, French, Japanese, Portuguese, Arabic, Czech, Italian, Korean, Dutch and Chinese; Russian is not listed. The hybrid architecture may have compatibility/performance differences in the current llama.cpp build, while the traditional `granite-4.0-1b-GGUF` has official GGUF and llama.cpp instructions. The official GGUF card warns that reduced-range variants can hit precision errors and recommends BF16 for full precision, which weakens its “works on any PC” position at comparable quality. Granite is a credible tool-calling/structured-output candidate for a second-stage test, but not a Russian-first default without local evaluation.

### Marco-Nano-Instruct

Marco-Nano-Instruct is Apache 2.0, multilingual with Russian listed, but is not a same-size dense model: 8B total parameters with only 0.6B activated per token, 7.5% activation ratio. Its model card reports strong vendor benchmarks versus Qwen3-1.7B and other baselines, including English average 62.8, multilingual general average 38.9 and cultural/regional average 59.1, but the model has 8B weights and needs a MoE-compatible runtime/quantization path. The card recommends vLLM; it states SGLang requires a specific commit. Because LocalComet currently uses llama.cpp and targets broad low-memory compatibility, Marco-Nano is an R&D candidate, not an immediate replacement.

## Preliminary ranking before local verification

1. Qwen3-1.7B: safest Russian-first replacement/upgrade path; Apache 2.0, 100+ languages, direct llama.cpp/tool-use evidence. 2. LFM2.5-1.2B-Instruct: best efficiency/quality candidate for English/agentic use, but Russian is not listed and the repository uses `lfm1.0` terms; must verify license compatibility and Russian quality before adoption. 3. Granite 4.0 1B/H-1B: strong Apache/tool-calling/structured-output candidate, but Russian is not listed and hybrid/precision compatibility requires testing. 4. Gemma 3 1B IT: multilingual candidate but Gemma terms. 5. SmolLM2-1.7B-Instruct: English-centric. 6. Marco-Nano-Instruct: efficient activation but 8B total MoE and runtime complexity.
2. Qwen3-1.7B: safest practical replacement/upgrade path; strong Russian and tool-use evidence, Apache 2.0, direct llama.cpp support.
3. Gemma 3 1B IT: interesting multilingual quality candidate but Gemma terms and uncertain Russian/tool routing reduce suitability as universal default.
4. SmolLM2-1.7B-Instruct: good English and function calling, but explicitly English-centric; not suitable as Russian-first default.
5. Marco-Nano-Instruct: impressive activated-parameter efficiency but 8B total MoE and runtime complexity make it unsuitable for the current broad-compatibility baseline without a separate engine experiment.

## Размеры опубликованных Q4_K_M артефактов

Ollama lists Qwen2.5-1.5B-Instruct Q4_K_M at 986MB and Qwen3-1.7B Q4_K_M at 1.4GB. The official LiquidAI LFM2.5-1.2B-Instruct-GGUF card lists Q4_K_M at 731MB. IBM's official Granite 4.0-1B GGUF card lists Q4_K_M at 1.02GB and warns about precision issues for reduced-range variants, recommending BF16 for full precision. These are repository artifact sizes, not total runtime RSS; context KV cache and llama.cpp buffers add memory.

### Qwen3 GGUF source for the LocalComet add-on

The official Qwen3-1.7B model card is safetensors/native format, while the practical GGUF source inspected for local use is `unsloth/Qwen3-1.7B-GGUF`, licensed Apache 2.0 and providing `Qwen3-1.7B-Q4_K_M.gguf` (about 1.11 GB) plus Unsloth Dynamic variants. This is a community quantization, not an official Qwen-maintained GGUF repository, so LocalComet should record the exact source/revision and SHA-256 after download. The selected artifact is the standard `Q4_K_M`, not the more aggressive IQ/UD variants, to reduce compatibility risk.

## Required local verification before changing LocalComet default

Run identical prompts and runtime settings for current Qwen2.5 1.5B, Qwen3-1.7B and LFM2.5-1.2B-Instruct: Russian factual answer, English answer, multi-turn context, structured output, code task, open_app Computer Use, new-chat transition, repeated tool calls, first-token latency, decode tok/s, peak memory, and failure recovery. Do not delete Qwen2.5 1.5B until a candidate passes the complete gate/smoke matrix.
