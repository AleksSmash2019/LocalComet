from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_PATH = ROOT / "desktop" / "localcomet-desktop" / "static" / "modelfit.html"
BUILD_PATH = ROOT / "desktop" / "localcomet-desktop" / "build" / "modelfit.html"
START_MARKER = "const wl=["
END_MARKER = "];function"

# The registry is deliberately curated around models with canonical cards and
# local GGUF workflows. New entries are inserted before the legacy first entry.
NEW_ENTRIES = {
    "qwen3.5-0.8b": '{id:"qwen3.5-0.8b",name:"Qwen3.5 0.8B",family:"Qwen",parametersB:0.8,sizeClass:"small",quantizations:D(0.8),useCases:["fast-chat","offline","russian"],languages:["en","ru","zh","201"],strengths:["Крайне лёгкая — работает на 4GB RAM","201 язык включая русский","Контекст 262K"],weaknesses:["Ограниченные рассуждения","Не подходит для сложных задач"],engines:[...T],ollamaTag:"qwen3.5:0.8b",hfRepo:"Qwen/Qwen3.5-0.8B",qualityScore:28,speedScore:99,hardwareDemandScore:4},',
    "qwen3.5-2b": '{id:"qwen3.5-2b",name:"Qwen3.5 2B",family:"Qwen",parametersB:2,sizeClass:"small",quantizations:D(2),useCases:["fast-chat","general","russian","offline"],languages:["en","ru","zh","201"],strengths:["Лучше Qwen3-1.7B по большинству метрик","201 язык","Агентские возможности","Контекст 262K"],weaknesses:["Не поддерживается в Ollama (только llama.cpp)","Мультимодальность требует отдельного mmproj"],engines:["llama.cpp","lm-studio","koboldcpp","text-generation-webui"],ollamaTag:"",hfRepo:"Qwen/Qwen3.5-2B",qualityScore:42,speedScore:93,hardwareDemandScore:8},',
    "qwen3.5-4b": '{id:"qwen3.5-4b",name:"Qwen3.5 4B",family:"Qwen",parametersB:4,sizeClass:"small",quantizations:D(4),useCases:["general","russian","coding","offline"],languages:["en","ru","zh","201"],strengths:["Агентские возможности уровня 7B","201 язык","Контекст 262K","Мультимодальность"],weaknesses:["Не поддерживается в Ollama (только llama.cpp)","Thinking-режим замедляет ответ"],engines:["llama.cpp","lm-studio","koboldcpp","text-generation-webui"],ollamaTag:"",hfRepo:"Qwen/Qwen3.5-4B",qualityScore:58,speedScore:82,hardwareDemandScore:17},',
    "phi4-mini": '{id:"phi4-mini",name:"Phi-4 Mini (3.8B)",family:"Phi",parametersB:3.8,sizeClass:"small",quantizations:D(3.8),useCases:["general","english","documents","coding","offline"],languages:["en","ru","zh","24"],strengths:["MIT лицензия","Сильные рассуждения для 3.8B","Tool use из коробки","Контекст 128K"],weaknesses:["Русский ограничен","Суховатый стиль"],engines:[...T,"directml","vllm"],ollamaTag:"phi4-mini",hfRepo:"microsoft/Phi-4-mini-instruct",qualityScore:55,speedScore:82,hardwareDemandScore:16},',
    "qwen3-vl-4b": '{id:"qwen3-vl-4b",name:"Qwen3-VL 4B",family:"Qwen",parametersB:4,sizeClass:"small",quantizations:D(4),useCases:["general","russian","documents","coding","offline"],languages:["en","ru","zh","multi"],strengths:["Vision и анализ документов","Отдельный mmproj опубликован вместе с GGUF","Apache-2.0","Q4_K_M около 2.5 GB"],weaknesses:["Для изображений нужен отдельный mmproj","Vision-запросы медленнее текста"],engines:[...T],ollamaTag:"qwen3-vl:4b",hfRepo:"Qwen/Qwen3-VL-4B-Instruct-GGUF",qualityScore:68,speedScore:78,hardwareDemandScore:19},',
    "qwen3-vl-8b": '{id:"qwen3-vl-8b",name:"Qwen3-VL 8B",family:"Qwen",parametersB:8,sizeClass:"medium",quantizations:D(8),useCases:["general","russian","documents","coding","best-quality"],languages:["en","ru","zh","multi"],strengths:["Сильное vision и video reasoning","Отдельный mmproj опубликован вместе с GGUF","Apache-2.0","Q4_K_M около 5.0 GB"],weaknesses:["Для изображений нужен отдельный mmproj","Требует заметно больше VRAM"],engines:[...T],ollamaTag:"qwen3-vl:8b",hfRepo:"Qwen/Qwen3-VL-8B-Instruct-GGUF",qualityScore:78,speedScore:62,hardwareDemandScore:35},',
    "ministral-3-3b": '{id:"ministral-3-3b",name:"Ministral 3 3B",family:"Mistral",parametersB:3.4,sizeClass:"small",quantizations:D(3.4),useCases:["general","documents","english","coding","offline"],languages:["en","fr","de","es","it","multi"],strengths:["Apache-2.0","Vision encoder и native function calling","Контекст 256K","Edge-ориентированная архитектура"],weaknesses:["Русский не является главным языком обучения","Для vision нужен multimodal-путь запуска"],engines:["llama.cpp","lm-studio","koboldcpp","text-generation-webui","vllm"],ollamaTag:"",hfRepo:"mistralai/Ministral-3-3B-Instruct-2512-GGUF",qualityScore:62,speedScore:78,hardwareDemandScore:18},',
    "gemma4-e2b": '{id:"gemma4-e2b",name:"Gemma 4 E2B (5B)",family:"Gemma",parametersB:5.1,sizeClass:"medium",quantizations:D(5.1),useCases:["general","documents","coding","english","offline"],languages:["en","multi"],strengths:["Apache-2.0","Мультимодальность: image, audio и text","Agent/function calling","Q4_K_M около 3.4 GB"],weaknesses:["E2B означает 2.3B effective и около 5.1B с embeddings","Для audio/vision нужны совместимые сборки"],engines:[...T],ollamaTag:"gemma4:e2b",hfRepo:"lmstudio-community/gemma-4-E2B-it-GGUF",qualityScore:64,speedScore:76,hardwareDemandScore:22},',
    "gemma4-e4b": '{id:"gemma4-e4b",name:"Gemma 4 E4B (8B)",family:"Gemma",parametersB:8,sizeClass:"medium",quantizations:D(8),useCases:["general","documents","coding","english","best-quality"],languages:["en","multi"],strengths:["Apache-2.0","Мультимодальность: image, audio и text","Agent/function calling","Q4_K_M около 5.3 GB"],weaknesses:["E4B означает 4.5B effective и около 8B с embeddings","Требует больше VRAM, чем E2B"],engines:[...T],ollamaTag:"gemma4:e4b",hfRepo:"lmstudio-community/gemma-4-E4B-it-GGUF",qualityScore:72,speedScore:68,hardwareDemandScore:34},',
    "gemma4-12b": '{id:"gemma4-12b",name:"Gemma 4 12B Unified",family:"Gemma",parametersB:12,sizeClass:"medium",quantizations:D(12),useCases:["general","documents","coding","best-quality","offline"],languages:["en","multi"],strengths:["Apache-2.0","Unified image/audio/text architecture","Контекст 256K","Q4_K_M около 7.4 GB"],weaknesses:["Медленнее малых Gemma/Qwen","Q6 уже близок к 10 GB до runtime overhead"],engines:[...T],ollamaTag:"gemma4:12b",hfRepo:"lmstudio-community/gemma-4-12B-it-GGUF",qualityScore:80,speedScore:52,hardwareDemandScore:52},',
    "phi4-14b": '{id:"phi4-14b",name:"Phi-4 (14B)",family:"Phi",parametersB:14,sizeClass:"large",quantizations:D(14),useCases:["general","english","documents","coding","best-quality","offline"],languages:["en"],strengths:["MIT лицензия","Сильная математика и reasoning","Q4 около 8.4 GB","Подходит для DirectML"],weaknesses:["Контекст всего 16K","Данные обучения имеют cutoff 2024","Английский-first"],engines:[...T,"directml","vllm"],ollamaTag:"phi4",hfRepo:"microsoft/phi-4-gguf",qualityScore:77,speedScore:46,hardwareDemandScore:54},',
    "qwen3-coder-30b-a3b": '{id:"qwen3-coder-30b-a3b",name:"Qwen3-Coder 30B A3B",family:"Qwen",parametersB:30.5,sizeClass:"large",quantizations:D(30.5),useCases:["coding","general","documents","best-quality","offline"],languages:["en","code","multi"],strengths:["Apache-2.0","30.5B total / 3.3B active MoE","Сильный tool calling и agentic coding","Контекст 262K"],weaknesses:["Q4_K_M около 18.6 GB — не для 12GB GPU","Большой общий вес даже при малом числе active experts"],engines:[...T,"vllm"],ollamaTag:"",hfRepo:"unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",qualityScore:90,speedScore:36,hardwareDemandScore:82},',
    "mistral-small-3.2-24b": '{id:"mistral-small-3.2-24b",name:"Mistral Small 3.2 24B",family:"Mistral",parametersB:24,sizeClass:"large",quantizations:D(24),useCases:["general","documents","coding","best-quality","english"],languages:["en","fr","de","es","it","24"],strengths:["Apache-2.0","Tool calling","Контекст 128K","Q4_K_M около 14.3 GB"],weaknesses:["Q4 не помещается в 12GB VRAM целиком","Q3 требует компромисса по качеству","Русский не является главным языком"],engines:[...T,"vllm"],ollamaTag:"",hfRepo:"unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF",qualityScore:82,speedScore:33,hardwareDemandScore:73},',
    "qwen3-30b-a3b": '{id:"qwen3-30b-a3b",name:"Qwen3 30B A3B",family:"Qwen",parametersB:30.5,sizeClass:"large",quantizations:D(30.5),useCases:["general","russian","documents","coding","best-quality"],languages:["en","ru","zh","100+"],strengths:["Apache-2.0","30B MoE с небольшим числом active experts","Thinking/non-thinking режимы","Сильный русский и tool use"],weaknesses:["Требует много RAM/VRAM даже в Q4","Медленная на обычном CPU"],engines:[...T,"vllm"],ollamaTag:"qwen3:30b",hfRepo:"Qwen/Qwen3-30B-A3B-GGUF",qualityScore:86,speedScore:38,hardwareDemandScore:82},',
}
NEW_MODEL_IDS = tuple(NEW_ENTRIES)


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_registry_bounds(html: str, path: Path) -> tuple[int, int]:
    starts = [match.start() for match in re.finditer(re.escape(START_MARKER), html)]
    if len(starts) != 1:
        raise RuntimeError(f"{path}: expected exactly one {START_MARKER!r}, found {len(starts)}")
    start = starts[0]
    end = html.find(END_MARKER, start + len(START_MARKER))
    if end < 0:
        raise RuntimeError(f"{path}: closing registry marker {END_MARKER!r} not found")
    if html.find(START_MARKER, start + len(START_MARKER)) >= 0:
        raise RuntimeError(f"{path}: a second registry marker appears after the first one")
    return start, end + 1


def repair_known_boundary(html: str, path: Path) -> str:
    start, end = extract_registry_bounds(html, path)
    registry = html[start:end]
    malformed_boundary = "hardwareDemandScore:16}{id:"
    if malformed_boundary not in registry:
        return html
    repaired_registry = registry.replace(malformed_boundary, "hardwareDemandScore:16},{id:", 1)
    return html[:start] + repaired_registry + html[end:]


def render_updated_html(html: str, path: Path) -> str:
    html = repair_known_boundary(html, path)
    start, end = extract_registry_bounds(html, path)
    registry = html[start:end]
    missing = [model_id for model_id in NEW_MODEL_IDS if f'id:"{model_id}"' not in registry]
    if not missing:
        return html

    body_start = start + len(START_MARKER)
    old_body = html[body_start:end]
    if not old_body.startswith("{id:"):
        raise RuntimeError(f"{path}: registry does not start with an object after {START_MARKER!r}")
    new_registry = START_MARKER + "".join(NEW_ENTRIES[model_id] for model_id in missing) + old_body
    return html[:start] + new_registry + html[end:]


def write_if_changed(path: Path, content: str) -> bool:
    if path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8", newline="")
    return True


def registry_entry(registry: str, model_id: str) -> str:
    entry_start = registry.index(f'id:"{model_id}"')
    entry_end = registry.find("},{id:", entry_start)
    if entry_end < 0:
        entry_end = len(registry)
    return registry[entry_start:entry_end]


def validate_registry(html: str, path: Path) -> None:
    start, end = extract_registry_bounds(html, path)
    registry = html[start:end]
    for model_id in NEW_MODEL_IDS:
        if registry.count(f'id:"{model_id}"') != 1:
            raise RuntimeError(f"{path}: expected exactly one entry for {model_id}")

    for model_id in ("qwen3.5-2b", "qwen3.5-4b"):
        entry = registry_entry(registry, model_id)
        expected_engines = 'engines:["llama.cpp","lm-studio","koboldcpp","text-generation-webui"]'
        if expected_engines not in entry:
            raise RuntimeError(f"{path}: {model_id} engine contract is incorrect")
        engines_end = entry.index(",ollamaTag:")
        engines = entry[entry.index("engines:"):engines_end]
        if "ollama" in engines.lower():
            raise RuntimeError(f"{path}: {model_id} must not advertise Ollama in engines")

    for model_id in ("qwen3-vl-4b", "qwen3-vl-8b"):
        entry = registry_entry(registry, model_id)
        if "mmproj" not in entry or "qwen3-vl" not in entry:
            raise RuntimeError(f"{path}: {model_id} must describe its separate mmproj requirement")

    if 'ollamaTag:"qwen3.5:0.8b"' not in registry_entry(registry, "qwen3.5-0.8b"):
        raise RuntimeError(f"{path}: qwen3.5-0.8b Ollama tag is missing")
    if 'hfRepo:"Qwen/Qwen3.5-0.8B"' not in registry_entry(registry, "qwen3.5-0.8b"):
        raise RuntimeError(f"{path}: qwen3.5-0.8b canonical HF repo is missing")


def main() -> int:
    if not STATIC_PATH.is_file():
        raise FileNotFoundError(STATIC_PATH)

    static_before = read_utf8(STATIC_PATH)
    static_after = render_updated_html(static_before, STATIC_PATH)
    validate_registry(static_after, STATIC_PATH)
    static_changed = write_if_changed(STATIC_PATH, static_after)

    build_changed = False
    if BUILD_PATH.is_file():
        build_before = read_utf8(BUILD_PATH)
        build_after = render_updated_html(build_before, BUILD_PATH)
        validate_registry(build_after, BUILD_PATH)
        build_changed = write_if_changed(BUILD_PATH, build_after)

    print(f"static={STATIC_PATH} changed={static_changed}")
    if BUILD_PATH.is_file():
        print(f"build={BUILD_PATH} changed={build_changed}")
    else:
        print(f"build={BUILD_PATH} present=False")
    print(f"added_or_verified_models={','.join(NEW_MODEL_IDS)}")
    print("registry_validation=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
