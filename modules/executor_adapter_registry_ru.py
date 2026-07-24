from __future__ import annotations

from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional

EXECUTOR_ADAPTER_VERSION = "v6.76"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _registry() -> List[Dict[str, Any]]:
    return [
        {
            "id": "opencode_deepseek",
            "title": "OpenCode with DeepSeek v4",
            "type": "local_ai",
            "strength": "Fast inference, strong coding capability",
            "weaknesses": "Limited context window, no vision",
            "allowed_task_types": ["code_generation", "code_review", "refactoring", "test_writing", "patch_creation"],
            "forbidden_task_types": ["sensitive_data_handling", "browser_automation", "external_api_calls"],
            "max_recommended_diff_files": 8,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Default development agent for LocalComet tasks.",
        },
        {
            "id": "opencode_qwen",
            "title": "OpenCode with Qwen-Coder",
            "type": "local_ai",
            "strength": "Good for open-ended research, alternative code perspective",
            "weaknesses": "Slower inference, may need more guidance",
            "allowed_task_types": ["code_review", "research", "architecture_exploration", "test_writing"],
            "forbidden_task_types": ["sensitive_data_handling", "browser_automation", "external_api_calls", "rapid_iteration"],
            "max_recommended_diff_files": 5,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Alternative model for code review and exploration.",
        },
        {
            "id": "opencode_north",
            "title": "OpenCode with North AI",
            "type": "hosted_ai",
            "strength": "Strong reasoning, large context",
            "weaknesses": "Requires internet, potentially higher cost",
            "allowed_task_types": ["complex_architecture", "security_audit", "large_refactoring"],
            "forbidden_task_types": ["rapid_iteration", "simple_patches"],
            "max_recommended_diff_files": 15,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Hosted model for complex tasks.",
        },
        {
            "id": "manual_patch",
            "title": "Manual Patch by Developer",
            "type": "human",
            "strength": "Full control, best for sensitive changes",
            "weaknesses": "Slow, requires developer time",
            "allowed_task_types": ["sensitive_data_handling", "security_patches", "critical_infrastructure"],
            "forbidden_task_types": [],
            "max_recommended_diff_files": 100,
            "requires_human_review": False,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": True,
            "status": "available",
            "notes": "Human developer makes changes manually.",
        },
        {
            "id": "chatgpt_manual_reviewer",
            "title": "ChatGPT Manual Reviewer",
            "type": "human_ai_review",
            "strength": "Human-in-the-loop AI review, independent perspective",
            "weaknesses": "No code execution, no file modification",
            "allowed_task_types": ["code_review", "validation_check", "architecture_review"],
            "forbidden_task_types": ["code_execution", "file_modification", "external_api_calls"],
            "max_recommended_diff_files": 20,
            "requires_human_review": True,
            "requires_green_gates": False,
            "can_execute_code": False,
            "can_modify_files": False,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Review-only adapter. Verdicts must be read via reviewer bridge.",
        },
        {
            "id": "local_ollama_future",
            "title": "Local Ollama Model (Future)",
            "type": "local_ai_future",
            "strength": "Fully offline, no API costs",
            "weaknesses": "Not yet configured, model TBD",
            "allowed_task_types": ["code_generation", "code_review"],
            "forbidden_task_types": ["sensitive_data_handling", "rapid_iteration"],
            "max_recommended_diff_files": 5,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "future",
            "notes": "Requires Ollama installation and model download.",
        },
        {
            "id": "internal_patch_engine_future",
            "title": "Internal Patch Engine (Future)",
            "type": "automated_future",
            "strength": "Fast automated patches for well-defined tasks",
            "weaknesses": "Not implemented, limited scope",
            "allowed_task_types": ["simple_patches", "test_writing"],
            "forbidden_task_types": ["sensitive_data_handling", "complex_architecture"],
            "max_recommended_diff_files": 3,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "future",
            "notes": "Future automated patch engine.",
        },
    ]


def get_executor_adapter_registry() -> List[Dict[str, Any]]:
    return _registry()


def get_executor_adapter(adapter_id: str) -> Optional[Dict[str, Any]]:
    for entry in _registry():
        if entry["id"] == adapter_id:
            return entry
    return None


def classify_executor_for_task(task_description: str) -> Dict[str, Any]:
    lower = task_description.lower().replace("ё", "е")
    recommendations = []
    for entry in _registry():
        for allowed in entry["allowed_task_types"]:
            if allowed.replace("_", " ") in lower:
                recommendations.append(entry["id"])
                break
    return {
        "ok": True,
        "task_description": task_description,
        "matched_adapters": recommendations,
    }


def recommend_executor(task_description: str = "") -> Dict[str, Any]:
    if not task_description:
        return {
            "ok": True,
            "mode": "executor_recommendation",
            "version": EXECUTOR_ADAPTER_VERSION,
            "recommendation": "opencode_deepseek",
            "reason": "Default adapter for general LocalComet development.",
        }
    classification = classify_executor_for_task(task_description)
    matched = classification.get("matched_adapters", [])
    if matched:
        return {
            "ok": True,
            "mode": "executor_recommendation",
            "version": EXECUTOR_ADAPTER_VERSION,
            "recommendation": matched[0],
            "all_matches": matched,
            "reason": f"Matched task description to adapter(s): {', '.join(matched)}",
        }
    return {
        "ok": True,
        "mode": "executor_recommendation",
        "version": EXECUTOR_ADAPTER_VERSION,
        "recommendation": "opencode_deepseek",
        "reason": "No specific match, defaulting to opencode_deepseek.",
    }


def status() -> Dict[str, Any]:
    registry = _registry()
    return {
        "ok": True,
        "mode": "executor_adapter_registry_status",
        "version": EXECUTOR_ADAPTER_VERSION,
        "total_adapters": len(registry),
        "available": [e["id"] for e in registry if e["status"] == "available"],
        "future": [e["id"] for e in registry if "future" in e["status"]],
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "executor_adapter_registry_report",
        "version": EXECUTOR_ADAPTER_VERSION,
        "generated_at": _now(),
        "registry": _registry(),
        "status": status(),
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"status", "executor adapter status", "pc executor adapter status"}:
        return status()
    if lower in {"report", "executor registry", "реестр исполнителей", "pc executor registry"}:
        return report()
    if lower in {"recommend executor", "какой исполнитель лучше", "pc recommend executor"}:
        return recommend_executor()
    if lower.startswith("recommend executor ") or lower.startswith("какой исполнитель лучше "):
        desc = lower.split(" ", 2)[-1] if len(lower.split(" ", 2)) > 2 else ""
        return recommend_executor(desc)
    return {
        "mode": "executor_adapter_registry_unrecognized",
        "version": EXECUTOR_ADAPTER_VERSION,
        "result": "Неизвестная команда. Используйте: executor registry, реестр исполнителей, executor adapter status, recommend executor, какой исполнитель лучше",
    }
