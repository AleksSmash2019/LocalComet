from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


PLAN_CONTRACT_VERSION = "v6.64"
PLAN_CONTRACT_NAME = "LocalComet Plan Contract Generator RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "agent"
PLAN_CONTRACT_JSON = OUTPUT_DIR / "plan_contract.json"
PLAN_CONTRACT_MD = OUTPUT_DIR / "plan_contract.md"
AGENTS_MD_PATH = ROOT_PATH / "AGENTS.md"
OPERATING_LAYER_PATH = ROOT_PATH / "docs" / "agent_operating_layer.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"
CONTEXT_PACK_PATH = ROOT_PATH / ".localcomet" / "agent" / "context_pack.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _line_with(path: Path, pattern: str) -> str:
    try:
        for line in path.read_text(encoding="utf-8").split("\n"):
            if pattern in line:
                return line.strip()
    except Exception:
        pass
    return ""


def _detect_base_version() -> str:
    line = _line_with(CONTROL_PANEL_PATH, "LOCALCOMET_VERSION")
    if "=" in line:
        return line.split("=")[-1].strip().strip("\"'")
    return "unknown"


def generate() -> Dict[str, Any]:
    base_version = _detect_base_version()
    agents_lines = []
    try:
        agents_lines = AGENTS_MD_PATH.read_text(encoding="utf-8").split("\n")[:5]
    except Exception:
        pass
    ol_lines = []
    if OPERATING_LAYER_PATH.exists():
        try:
            ol_lines = OPERATING_LAYER_PATH.read_text(encoding="utf-8").split("\n")[:3]
        except Exception:
            pass
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
        "task_goal": "",
        "risk_level": "unclassified",
        "allowed_files": [],
        "forbidden_files": [],
        "expected_outputs": [],
        "validation_gates": [
            "py_compile",
            "contract_tests",
            "functional_tests",
            "strict_project_stability",
        ],
        "rollback_policy": {
            "restore_from_backup_if_any_gate_fails": True,
            "no_partial_green_claims": True,
        },
        "final_report_requirements": [
            "backup path",
            "files changed",
            "exact validation commands run",
            "contract tests actual count",
            "functional tests actual count",
            "strict_project_stability result",
            "smoke test result",
            "final GREEN status",
            "residual risks",
        ],
        "agent_rules": [
            "Read AGENTS.md before editing",
            "Create backup + manifest before every edit",
            "Run full validation after every edit",
            "Only GREEN is acceptable",
            "Do not weaken safety checks",
            "Do not commit secrets",
            "Do not add network calls",
            "Do not add production dependencies without approval",
            "Prefer minimal safe changes over large rewrites",
        ],
        "source_references": {
            "agents_md": {
                "path": str(AGENTS_MD_PATH.relative_to(ROOT_PATH)),
                "first_lines": "\n".join(agents_lines),
            },
            "operating_layer": {
                "path": str(OPERATING_LAYER_PATH.relative_to(ROOT_PATH)) if OPERATING_LAYER_PATH.exists() else "",
                "exists": OPERATING_LAYER_PATH.exists(),
                "first_lines": "\n".join(ol_lines),
            },
            "context_pack": {
                "path": str(CONTEXT_PACK_PATH.relative_to(ROOT_PATH)) if context_pack_exists else "",
                "exists": context_pack_exists,
                "base_version": context_pack_version,
            },
        },
    }


def _write_plan_contract(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_CONTRACT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# LocalComet Plan Contract",
        "",
        f"- schema_version: {payload.get('schema_version')}",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- risk_level: {payload.get('risk_level')}",
        "",
        "## Task Goal",
        "",
        f"{payload.get('task_goal', '')}",
        "",
        "## Allowed Files",
        "",
    ]
    for af in payload.get("allowed_files", []):
        lines.append(f"- {af}")
    lines.append("")
    lines.extend(["## Forbidden Files", ""])
    for ff in payload.get("forbidden_files", []):
        lines.append(f"- {ff}")
    lines.append("")
    lines.extend(["## Expected Outputs", ""])
    for eo in payload.get("expected_outputs", []):
        lines.append(f"- {eo}")
    lines.append("")
    lines.extend(["## Validation Gates", ""])
    for vg in payload.get("validation_gates", []):
        lines.append(f"- {vg}")
    lines.append("")
    lines.extend(["## Rollback Policy", ""])
    rp = payload.get("rollback_policy", {})
    if isinstance(rp, dict):
        for k, v in rp.items():
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Final Report Requirements", ""])
    for fr in payload.get("final_report_requirements", []):
        lines.append(f"- {fr}")
    lines.append("")
    lines.extend(["## Agent Rules", ""])
    for ar in payload.get("agent_rules", []):
        lines.append(f"- {ar}")
    lines.append("")
    lines.extend(["## Source References", ""])
    refs = payload.get("source_references", {})
    if isinstance(refs, dict):
        agents = refs.get("agents_md", {})
        if isinstance(agents, dict) and agents.get("path"):
            lines.append(f"- AGENTS.md: {agents['path']}")
            first = agents.get("first_lines", "")
            if first:
                lines.append("  ```text")
                lines.append(f"  {first}")
                lines.append("  ```")
        lines.append("")
        ol = refs.get("operating_layer", {})
        if isinstance(ol, dict) and ol.get("exists"):
            lines.append(f"- docs/agent_operating_layer.md: {ol['path']}")
            first = ol.get("first_lines", "")
            if first:
                lines.append("  ```text")
                lines.append(f"  {first}")
                lines.append("  ```")
        lines.append("")
        cp = refs.get("context_pack", {})
        if isinstance(cp, dict) and cp.get("exists"):
            lines.append(f"- context_pack.json: {cp['path']} (base_version: {cp.get('base_version', '')})")
        lines.append("")
    PLAN_CONTRACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(PLAN_CONTRACT_JSON.relative_to(ROOT_PATH)), "md": str(PLAN_CONTRACT_MD.relative_to(ROOT_PATH))}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "plan_contract_status",
        "version": PLAN_CONTRACT_VERSION,
        "json_exists": PLAN_CONTRACT_JSON.exists(),
        "md_exists": PLAN_CONTRACT_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = generate()
    paths = _write_plan_contract(payload)
    return {
        "ok": True,
        "mode": "plan_contract_report",
        "version": PLAN_CONTRACT_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_plan_contract_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet agent plan contract",
        "agent plan contract",
        "plan contract",
    } or lowered.startswith("localcomet agent plan contract ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet agent plan contract", "agent plan contract", "plan contract"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "plan_contract_generated", "version": PLAN_CONTRACT_VERSION, "paths": result.get("paths", {})}
    if lowered.startswith("localcomet agent plan contract "):
        result = report()
        return {"ok": True, "handled": True, "mode": "plan_contract_generated", "version": PLAN_CONTRACT_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet agent plan contract status", "agent plan contract status", "plan contract status"}:
        return status()
    return {"ok": False, "mode": "plan_contract_unknown", "version": PLAN_CONTRACT_VERSION, "command": command, "hint": "Use: localcomet agent plan contract"}


if __name__ == "__main__":
    result = dispatch("localcomet agent plan contract")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
