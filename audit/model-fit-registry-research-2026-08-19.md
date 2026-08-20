# ModelFit registry research — 2026-08-19

## Sources and verified facts

1. Qwen3.5-2B official model card: https://huggingface.co/Qwen/Qwen3.5-2B
   - License: Apache-2.0.
   - 2B parameters; native context length 262,144.
   - Supports text and vision-language input; model card describes agent/tool use and local-app deployment.
   - Official benchmark table reports Qwen3.5-2B above Qwen3-1.7B on multiple language, reasoning, multilingual and agent metrics, while still remaining a 2B model.
   - Non-thinking mode is the default; the model card documents tool-call parser examples for Qwen3.5.

2. Qwen3.5-2B GGUF community quantization: https://huggingface.co/lmstudio-community/Qwen3.5-2B-GGUF
   - License: Apache-2.0 inherited from Qwen3.5-2B.
   - GGUF Q4_K_M is listed at 1.27 GB; Q6_K 1.56 GB; Q8_0 2.01 GB.
   - The card explicitly documents llama.cpp and Windows local serving.
   - Quantization was produced by the LM Studio team using llama.cpp b8185; actual LocalComet runtime is b10068, so runtime compatibility must be tested rather than assumed.

3. Qwen3-1.7B official model card: https://huggingface.co/Qwen/Qwen3-1.7B
   - License: Apache-2.0.
   - 1.7B parameters, context length 32,768, 100+ languages/dialects and documented agent/tool capabilities.
   - The card explicitly lists llama.cpp, Ollama and LM Studio as supported local applications.
   - Qwen3 supports thinking/non-thinking switching; the card notes recommended sampling and possible endless repetitions if sampling is misconfigured.

4. Microsoft Phi-4-mini-instruct model card: https://huggingface.co/microsoft/Phi-4-mini-instruct
   - License: MIT.
   - 3.8B parameters, 128K context, multilingual support including Russian, and documented tool-enabled function-calling format.
   - Model card positions it for memory/compute constrained and latency-bound environments, but also warns that non-English quality is uneven and that tool use must be evaluated in the target application.

## Registry implication

The current bundled registry contains stale 2024-era families and inflated heuristic scores. The first candidate to add/update is Qwen3.5-2B Q4_K_M as the current small general model, while keeping Qwen3-1.7B as the proven fallback and Qwen2.5 1.5B as the lowest-resource baseline. Phi-4-mini-instruct is a useful MIT-licensed English/reasoning alternative, but should not outrank Qwen models for Russian-first default selection without a LocalComet smoke test.

Do not add a model solely from a search snippet. Every entry must include a canonical model card URL, explicit license, quantization/size source, CPU/GPU fit assumptions and a compatibility status in LocalComet.

## Browser verification

The official Hugging Face page for Qwen/Qwen3.5-2B was opened in the authenticated browser session. The visible card confirms Apache-2.0, the Image-Text-to-Text task, a 2B parameter model, a native 262,144-token context, and a Browse Quantizations route explicitly covering llama.cpp, Ollama and LM Studio. The page also documents the model as a multimodal/agent-oriented model and lists Qwen3.5-2B benchmark columns against Qwen3-1.7B.

The official GGUF page was also opened in the browser. It confirms Apache-2.0, Q4_K_M at 1.27 GB, Q6_K at 1.56 GB and Q8_0 at 2.01 GB. It explicitly documents Windows llama.cpp commands for the Q4_K_M artifact and identifies LM Studio/llama.cpp b8185 as the quantizer source. This is sufficient to add Qwen3.5-2B as a verified recommendation candidate, but the LocalComet b10068 runtime still requires an in-app smoke test.

## Additional browser verification

The official Qwen/Qwen3.5-0.8B page confirms Apache-2.0, 0.8B parameters, native 262,144-token context, 201-language coverage and links to llama.cpp, LM Studio, Jan and Ollama quantizations. The official Qwen/Qwen3.5-4B page confirms Apache-2.0, 4B parameters, native 262,144-token context (extensible to 1,010,000), a vision encoder and 201-language coverage. These facts support the small sizeClass for 0.8B/2B/4B in ModelFit, with Q4_K_M-derived hardware estimates from the shared D() function.

## Expansion research — current session

The official Ministral-3-3B-Instruct-2512-GGUF card confirms Apache-2.0, a 3B model made of a 3.4B language model plus a 0.4B vision encoder, native function calling/JSON output, vision, dozens of languages, 256K context, and edge deployment. Its visible GGUF sizes are Q4_K_M 2.15 GB, Q5_K_M 2.47 GB, Q8_0 3.65 GB and BF16 6.87 GB. The card is suitable as a canonical llama.cpp-compatible recommendation candidate.

The official Hugging Face Gemma 4 announcement confirms Apache-2 licensing, multimodal image/text/audio support, agent/function-calling and local deployment via llama.cpp, MLX, WebGPU and Rust. It lists Gemma 4 E2B (2.3B effective / 5.1B with embeddings, 128K), E4B (4.5B effective / 8B with embeddings, 128K), 12B Unified (256K), 26B A4B MoE and 31B. Gemma 4 E2B and E4B are the most relevant additions for local ModelFit; exact GGUF sizes must be read from their canonical quantization cards before insertion.

Canonical GGUF verification for Gemma 4 small variants: lmstudio-community/gemma-4-E2B-it-GGUF is Apache-2.0 and lists Q4_K_M 3.43 GB, Q6_K 3.85 GB and Q8_0 4.97 GB, with Windows llama.cpp commands and Ollama/LM Studio/Jan integrations. lmstudio-community/gemma-4-E4B-it-GGUF is Apache-2.0 and lists Q4_K_M 5.34 GB, Q6_K 6.22 GB and Q8_0 8.03 GB, also with Windows llama.cpp commands. Both cards identify the Google base/instruct model and LM Studio llama.cpp quantization releases b10076/b10069 respectively.

The official Qwen/Qwen3-Coder-30B-A3B-Instruct card confirms Apache-2.0, 30.5B total parameters with 3.3B activated, native 262K context, agentic coding/tool calling, and local support references for Ollama, LM Studio, MLX, llama.cpp and KTransformers. It is a strong large coding/agent candidate; a canonical GGUF card and exact Q4 size should be used for the registry entry.

The Unsloth Mistral-Small-3.2-24B-Instruct-2506-GGUF card confirms Apache-2.0, 24B parameters, 24 languages, 128K context and tool-calling chat templates. It exposes a broad quantization ladder; Q4_K_M is 14.3 GB, Q3_K_M 11.5 GB, Q5_K_M 16.8 GB and Q8_0 25.1 GB. For the user's 12GB RTX 5070, this model is not a full-GPU candidate at Q4; if added, ModelFit must mark it as partial/CPU or recommend Q3 only with an explicit quality trade-off.

The canonical Unsloth Qwen3-Coder-30B-A3B-Instruct-GGUF card confirms Apache-2.0, 30.5B total/3.3B activated parameters, native 262K context, tool calling and local llama.cpp/Ollama/LM Studio support. Visible quant sizes include Q2_K 11.3 GB, Q3_K_M 14.7 GB, Q4_K_M 18.6 GB and Q5_K_M 21.7 GB. It should be represented as a large partial/CPU-oriented coding agent rather than a full-GPU recommendation for a 12GB RTX 5070.

The official Qwen/Qwen3-VL-4B-Instruct-GGUF card confirms Apache-2.0, Q4_K_M 2.5 GB, Q8_0 4.28 GB and F16 8.05 GB. The repository explicitly separates the language model and vision encoder (mmproj), with FP16/Q8_0 vision files, and documents compatibility with llama.cpp, Ollama, CPU, CUDA, Metal and SYCL. This should be recorded as a vision-specific model with a separate mmproj requirement, not as a text-only drop-in.

The official Qwen/Qwen3-VL-8B-Instruct-GGUF card confirms Apache-2.0, Q4_K_M 5.03 GB, Q8_0 8.71 GB and F16 16.4 GB. Like the 4B variant, it is split into an LLM and a separate mmproj vision encoder and supports llama.cpp, Ollama, CPU, CUDA, Metal and SYCL. It is a distinct vision model and should be surfaced with an explicit mmproj note.

Microsoft's official phi-4-gguf card confirms MIT licensing, a dense 14B architecture, 16K context and Q4_K_S 8.44 GB, Q5_K_S 10.2 GB, Q6_K 12 GB and Q8_0 15.6 GB. It is a text-only reasoning/coding alternative, but its data cutoff is June 2024 and context is much shorter than current Qwen/Gemma models; scores should reflect that limitation.
