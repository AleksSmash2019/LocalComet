from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_PATH = ROOT / "desktop" / "localcomet-desktop" / "static" / "modelfit.html"
BUILD_PATH = ROOT / "desktop" / "localcomet-desktop" / "build" / "modelfit.html"
MODEL_IDS = (
    "qwen3.5-0.8b",
    "qwen3.5-2b",
    "qwen3.5-4b",
    "phi4-mini",
    "qwen3-vl-4b",
    "qwen3-vl-8b",
    "ministral-3-3b",
    "gemma4-e2b",
    "gemma4-e4b",
    "gemma4-12b",
    "phi4-14b",
    "qwen3-coder-30b-a3b",
    "mistral-small-3.2-24b",
    "qwen3-30b-a3b",
)


def registry(path: Path) -> str:
    html = path.read_text(encoding="utf-8")
    start = html.index("const wl=[")
    end = html.index("];function", start) + 1
    return html[start:end]


def entry(text: str, model_id: str) -> str:
    start = text.index(f'id:"{model_id}"')
    end = text.find("},{id:", start)
    if end < 0:
        end = len(text)
    return text[start:end]


def main() -> int:
    for path in (STATIC_PATH, BUILD_PATH):
        if not path.is_file():
            print(f"{path}: present=False")
            continue
        text = registry(path)
        print(f"{path}: present=True registry_chars={len(text)}")
        for model_id in MODEL_IDS:
            count = text.count(f'id:"{model_id}"')
            print(f"{model_id}_count={count}")
            if count != 1:
                raise RuntimeError(f"{path}: expected exactly one entry for {model_id}")

        for model_id in ("qwen3.5-2b", "qwen3.5-4b"):
            model_entry = entry(text, model_id)
            expected = 'engines:["llama.cpp","lm-studio","koboldcpp","text-generation-webui"]'
            if expected not in model_entry:
                raise RuntimeError(f"{path}: {model_id} engine contract is incorrect")
            engines_end = model_entry.index(",ollamaTag:")
            engines = model_entry[model_entry.index("engines:"):engines_end]
            if "ollama" in engines.lower():
                raise RuntimeError(f"{path}: {model_id} incorrectly advertises Ollama")
            print(f"{model_id}_engines={engines}")

        for model_id in ("qwen3-vl-4b", "qwen3-vl-8b"):
            model_entry = entry(text, model_id)
            if "mmproj" not in model_entry or "GGUF" not in model_entry[model_entry.index("hfRepo:"):]:
                raise RuntimeError(f"{path}: {model_id} must describe separate mmproj GGUF workflow")
            print(f"{model_id}_mmproj=present")

        required_repos = {
            "ministral-3-3b": "mistralai/Ministral-3-3B-Instruct-2512-GGUF",
            "gemma4-e2b": "lmstudio-community/gemma-4-E2B-it-GGUF",
            "gemma4-e4b": "lmstudio-community/gemma-4-E4B-it-GGUF",
            "gemma4-12b": "lmstudio-community/gemma-4-12B-it-GGUF",
            "phi4-14b": "microsoft/phi-4-gguf",
            "qwen3-coder-30b-a3b": "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",
            "mistral-small-3.2-24b": "unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF",
            "qwen3-30b-a3b": "Qwen/Qwen3-30B-A3B-GGUF",
        }
        for model_id, repo in required_repos.items():
            if f'hfRepo:"{repo}"' not in entry(text, model_id):
                raise RuntimeError(f"{path}: {model_id} canonical repo mismatch")

    print("verification=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
