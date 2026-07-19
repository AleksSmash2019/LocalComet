from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


RISK_CLASSIFIER_VERSION = "v6.64"
RISK_CLASSIFIER_NAME = "LocalComet Risk Classifier RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "agent"
RISK_CLASSIFIER_JSON = OUTPUT_DIR / "risk_classification.json"
RISK_CLASSIFIER_MD = OUTPUT_DIR / "risk_classification.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"
CONTEXT_PACK_PATH = ROOT_PATH / ".localcomet" / "agent" / "context_pack.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _detect_base_version() -> str:
    try:
        for line in CONTROL_PANEL_PATH.read_text(encoding="utf-8").split("\n"):
            if "LOCALCOMET_VERSION" in line and "=" in line:
                return line.split("=")[-1].strip().strip("\"'")
    except Exception:
        pass
    return "unknown"


_CLASSIFIERS: List[Tuple[str, List[str], str]] = [
    ("docs_only", [
        "docs", "readme", "agients.md", "markdown", "documentation",
        "comment", "typo", "wording", "baseline", "cosmetic", ".md",
    ], "Task mentions only documentation, comments, or cosmetic text changes."),
    ("tests_only", [
        "test", "contract", "functional test", "regression",
        "test registration", "test coverage",
    ], "Task primarily mentions tests or test registration."),
    ("low", [
        "passive", "generator", "schema", "report", "template",
        "context pack", "plan contract", "artifact", "handoff",
    ], "Passive generator or schema-only addition. No runtime change."),
    ("medium", [
        "module creation", "dispatch integration", "control bridge",
        "command routing", "file writes", "bridge", "outer bridge",
        "control panel", "route",
    ], "Creates or wires a new module. Changes control flow."),
    ("high", [
        "runtime behavior", "automation", "execute", "subprocess",
        "agent invocation", "open code", "external agent",
        "network", "dependency", "installer", "install package",
        "security", "auth", "secrets", "credential",
        "delete", "deletion", "migration", "dangerous",
    ], "Changes runtime behavior, invokes external code, or touches security."),
]


_RISK_SCORE_MAP: Dict[str, int] = {
    "unclassified": 0,
    "docs_only": 1,
    "tests_only": 2,
    "low": 3,
    "medium": 5,
    "high": 8,
}

_RECOMMENDATIONS_MAP: Dict[str, List[str]] = {
    "unclassified": ["Provide a detailed task goal for accurate risk assessment."],
    "docs_only": ["Safe to proceed. No code runtime changes."],
    "tests_only": ["Safe to proceed. Tests do not alter production runtime behavior."],
    "low": ["Safe to proceed. Passive generator or schema-only addition."],
    "medium": ["Review control-flow changes before merging.", "Ensure contract tests cover the new route."],
    "high": ["Requires careful review.", "Verify safety checks before execution.", "Block automated GUI-only execution."],
}


def classify(task_goal: str) -> Dict[str, Any]:
    goal = str(task_goal or "").strip().lower()
    if not goal:
        return {
            "risk_level": "unclassified",
            "risk_score": _RISK_SCORE_MAP["unclassified"],
            "risk_reasons": ["No task goal provided. Risk cannot be assessed."],
        }
    matched_level = "unclassified"
    matched_reasons: List[str] = []
    for level, keywords, reason in _CLASSIFIERS:
        for kw in keywords:
            if kw in goal:
                matched_level = level
                matched_reasons.append(reason)
                break
    if not matched_reasons:
        matched_reasons.append("No risk classification keywords matched the task goal.")
    return {
        "risk_level": matched_level,
        "risk_score": _RISK_SCORE_MAP.get(matched_level, 0),
        "risk_reasons": matched_reasons,
    }


def generate(task_goal: str = "") -> Dict[str, Any]:
    base_version = _detect_base_version()
    result = classify(task_goal)
    context_pack_exists = CONTEXT_PACK_PATH.exists()
    context_pack_version = ""
    if context_pack_exists:
        try:
            cp = json.loads(CONTEXT_PACK_PATH.read_text(encoding="utf-8"))
            context_pack_version = cp.get("base_version", "")
        except Exception:
            pass
    return {
        "schema_version": "1.0",
        "project_name": "LocalComet",
        "base_version": base_version,
        "generated_at": _now(),
        "task_goal": task_goal,
        "risk_level": result["risk_level"],
        "risk_score": result.get("risk_score", 0),
        "risk_reasons": result["risk_reasons"],
        "recommendations": _RECOMMENDATIONS_MAP.get(result["risk_level"], []),
        "allowed_files": [],
        "forbidden_files": [
            "secrets",
            "credentials",
            "relay installer default workflow",
        ],
        "validation_intensity": "full_green_required",
        "required_gates": [
            "py_compile",
            "contract_tests",
            "functional_tests",
            "strict_project_stability",
        ],
        "review_requirements": [
            "explicit final GREEN status",
            "exact validation commands",
            "residual risks",
        ],
        "rollback_policy": {
            "restore_from_backup_if_any_gate_fails": True,
            "no_partial_green_claims": True,
        },
        "source_references": {
            "context_pack": {
                "path": str(CONTEXT_PACK_PATH.relative_to(ROOT_PATH)) if context_pack_exists else "",
                "exists": context_pack_exists,
                "base_version": context_pack_version,
            },
        },
    }


def _write_classification(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RISK_CLASSIFIER_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# LocalComet Risk Classification",
        "",
        f"- schema_version: {payload.get('schema_version')}",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- risk_level: {payload.get('risk_level')}",
        f"- risk_score: {payload.get('risk_score', 0)}",
        "",
        "## Task Goal",
        "",
        f"{payload.get('task_goal', '')}",
        "",
        "## Risk Reasons",
        "",
    ]
    for rr in payload.get("risk_reasons", []):
        lines.append(f"- {rr}")
    lines.append("")
    lines.extend(["## Recommendations", ""])
    for rec in payload.get("recommendations", []):
        lines.append(f"- {rec}")
    lines.append("")
    lines.extend(["## Allowed Files", ""])
    for af in payload.get("allowed_files", []):
        lines.append(f"- {af}")
    lines.append("")
    lines.extend(["## Forbidden Files", ""])
    for ff in payload.get("forbidden_files", []):
        lines.append(f"- {ff}")
    lines.append("")
    lines.extend(["## Validation Intensity", "", f"{payload.get('validation_intensity', '')}", ""])
    lines.extend(["## Required Gates", ""])
    for rg in payload.get("required_gates", []):
        lines.append(f"- {rg}")
    lines.append("")
    lines.extend(["## Review Requirements", ""])
    for rr in payload.get("review_requirements", []):
        lines.append(f"- {rr}")
    lines.append("")
    lines.extend(["## Rollback Policy", ""])
    rp = payload.get("rollback_policy", {})
    if isinstance(rp, dict):
        for k, v in rp.items():
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Source References", ""])
    cp_ref = payload.get("source_references", {}).get("context_pack", {})
    if isinstance(cp_ref, dict) and cp_ref.get("exists"):
        lines.append(f"- context_pack.json: {cp_ref['path']} (base_version: {cp_ref.get('base_version', '')})")
    lines.append("")
    RISK_CLASSIFIER_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(RISK_CLASSIFIER_JSON.relative_to(ROOT_PATH)), "md": str(RISK_CLASSIFIER_MD.relative_to(ROOT_PATH))}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "risk_classifier_status",
        "version": RISK_CLASSIFIER_VERSION,
        "json_exists": RISK_CLASSIFIER_JSON.exists(),
        "md_exists": RISK_CLASSIFIER_MD.exists(),
    }


def report(task_goal: str = "") -> Dict[str, Any]:
    payload = generate(task_goal)
    paths = _write_classification(payload)
    return {
        "ok": True,
        "mode": "risk_classifier_report",
        "version": RISK_CLASSIFIER_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_risk_classifier_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet agent risk classify",
        "agent risk classify",
        "risk classify",
    } or lowered.startswith("localcomet agent risk classify ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    task_goal = ""
    if lowered in {"localcomet agent risk classify", "agent risk classify", "risk classify"}:
        task_goal = ""
    elif lowered.startswith("localcomet agent risk classify "):
        task_goal = command[len("localcomet agent risk classify "):].strip()
    elif lowered in {"localcomet agent risk classify status", "agent risk classify status", "risk classify status"}:
        return status()
    else:
        return {"ok": False, "mode": "risk_classifier_unknown", "version": RISK_CLASSIFIER_VERSION, "command": command, "hint": "Use: localcomet agent risk classify [task goal]"}
    result = report(task_goal)
    return {"ok": True, "handled": True, "mode": "risk_classifier_generated", "version": RISK_CLASSIFIER_VERSION, "paths": result.get("paths", {})}


if __name__ == "__main__":
    result = dispatch("localcomet agent risk classify")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
