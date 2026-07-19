from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


CONTEXT_PACK_VERSION = "v6.64"
CONTEXT_PACK_NAME = "LocalComet Context Pack Generator RU"

ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_PATH / ".localcomet" / "agent"
CONTEXT_PACK_JSON = OUTPUT_DIR / "context_pack.json"
CONTEXT_PACK_MD = OUTPUT_DIR / "context_pack.md"
SCHEMA_PATH = ROOT_PATH / ".localcomet" / "agent" / "run_manifest.schema.json"
AGENTS_MD_PATH = ROOT_PATH / "AGENTS.md"
OPERATING_LAYER_PATH = ROOT_PATH / "docs" / "agent_operating_layer.md"
CONTROL_PANEL_PATH = ROOT_PATH / "LocalComet_Control_Panel.py"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_line_with(path: Path, pattern: str) -> str:
    try:
        for line in path.read_text(encoding="utf-8").split("\n"):
            if pattern in line:
                return line.strip()
    except Exception:
        pass
    return ""


def _extract_green_baseline() -> Dict[str, Any]:
    baseline = {
        "version": "unknown",
        "strict_project_stability": "unknown",
        "functional": "unknown",
        "contracts": "unknown",
        "hard_failures": "unknown",
        "warnings": "unknown",
    }
    try:
        text = AGENTS_MD_PATH.read_text(encoding="utf-8")
        for line in text.split("\n"):
            if "LOCALCOMET_VERSION" in line:
                baseline["version"] = line.split("=")[-1].strip()
            if "strict_project_stability:" in line:
                baseline["strict_project_stability"] = line.split(":")[-1].strip().split(",")[0]
            if "hard_failures=" in line:
                for p in line.split(","):
                    p = p.strip()
                    if "hard_failures=" in p:
                        baseline["hard_failures"] = p.split("=")[-1]
                    if "warnings=" in p:
                        baseline["warnings"] = p.split("=")[-1]
            if "functional:" in line:
                baseline["functional"] = line.split(":")[-1].strip()
            if "contracts:" in line:
                baseline["contracts"] = line.split(":")[-1].strip()
    except Exception:
        pass
    return baseline


def _detect_base_version() -> str:
    line = _read_line_with(CONTROL_PANEL_PATH, "LOCALCOMET_VERSION")
    if "=" in line:
        return line.split("=")[-1].strip().strip("\"'")
    return "unknown"


def generate() -> Dict[str, Any]:
    baseline = _extract_green_baseline()
    base_version = _detect_base_version()
    schema_ok = SCHEMA_PATH.exists() and SCHEMA_PATH.is_file()
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

    return {
        "project_name": "LocalComet / LocalAgent",
        "base_version": base_version,
        "current_green_baseline": baseline,
        "task_goal": "",
        "timestamp": _now(),
        "allowed_files": [],
        "forbidden_files": [],
        "validation_commands": [
            "python -m py_compile <changed_python_file>",
            "python -m py_compile LocalComet_Control_Panel.py",
            "python tools\\localcomet_preflight_audit.py --include-tools",
            "python -c \"from modules.computer_use_core_ru import dispatch; r=dispatch('pc computer contracts'); print(r); assert r['ok']\"",
            "python -c \"from modules.strict_project_stability_ru import dispatch; r=dispatch('\\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u044c \\u043f\\u0440\\u043e\\u0435\\u043a\\u0442'); assert r['ok'] and r['summary']['hard_failures'] == 0 and r['summary']['warnings'] == 0\"",
        ],
        "required_final_report_fields": [
            "files_changed",
            "backup_path",
            "tests_run",
            "test_results",
            "first_failing_error",
            "rollback_instructions",
            "project_is_green",
        ],
        "stability_policy": "Only GREEN is acceptable. If any gate fails, revert or fix before proceeding.",
        "relay_installer_policy": "For architecture-only edits (docs, schemas, skills, config), do NOT use the Relay installer workflow. Use direct file writes. The Relay installer workflow is for product changes only.",
        "notes_for_opencode": "",
        "agents_md_reference": {
            "path": str(AGENTS_MD_PATH.relative_to(ROOT_PATH)),
            "first_lines": "\n".join(agents_lines),
        },
        "operating_layer_reference": {
            "path": str(OPERATING_LAYER_PATH.relative_to(ROOT_PATH)) if OPERATING_LAYER_PATH.exists() else "",
            "exists": OPERATING_LAYER_PATH.exists(),
            "first_lines": "\n".join(ol_lines),
        },
        "schema_validated": {
            "path": str(SCHEMA_PATH.relative_to(ROOT_PATH)),
            "exists": schema_ok,
        },
    }


def _write_context_pack(payload: Dict[str, Any]) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_PACK_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# LocalComet Context Pack",
        "",
        f"- project_name: {payload.get('project_name')}",
        f"- base_version: {payload.get('base_version')}",
        f"- generated_at: {payload.get('timestamp')}",
        "",
        "## Current GREEN Baseline",
        "",
    ]
    bl = payload.get("current_green_baseline", {})
    if isinstance(bl, dict):
        for k, v in bl.items():
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.extend(["## Task Goal", "", f"{payload.get('task_goal', '')}", ""])
    lines.extend(["## Allowed Files", ""])
    for af in payload.get("allowed_files", []):
        lines.append(f"- {af}")
    lines.append("")
    lines.extend(["## Forbidden Files", ""])
    for ff in payload.get("forbidden_files", []):
        lines.append(f"- {ff}")
    lines.append("")
    lines.extend(["## Validation Commands", ""])
    for vc in payload.get("validation_commands", []):
        lines.append(f"```powershell\n{vc}\n```")
    lines.append("")
    lines.extend(["## Required Final Report Fields", ""])
    for rf in payload.get("required_final_report_fields", []):
        lines.append(f"- {rf}")
    lines.append("")
    lines.extend(["## Stability Policy", "", payload.get("stability_policy", ""), ""])
    lines.extend(["## Relay Installer Policy", "", payload.get("relay_installer_policy", ""), ""])
    lines.extend(["## Notes for OpenCode", "", payload.get("notes_for_opencode", ""), ""])
    lines.extend(["## References", ""])
    ref = payload.get("agents_md_reference", {})
    if isinstance(ref, dict) and ref.get("path"):
        lines.append(f"- AGENTS.md: {ref['path']}")
        first = ref.get("first_lines", "")
        if first:
            lines.append("  ```text")
            lines.append(f"  {first}")
            lines.append("  ```")
    lines.append("")
    ref2 = payload.get("operating_layer_reference", {})
    if isinstance(ref2, dict) and ref2.get("exists"):
        lines.append(f"- docs/agent_operating_layer.md: {ref2['path']}")
        first = ref2.get("first_lines", "")
        if first:
            lines.append("  ```text")
            lines.append(f"  {first}")
            lines.append("  ```")
    lines.append("")
    sv = payload.get("schema_validated", {})
    if isinstance(sv, dict):
        lines.append(f"- run_manifest.schema.json: {sv.get('path', '')} (exists: {sv.get('exists', False)})")
    lines.append("")
    CONTEXT_PACK_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(CONTEXT_PACK_JSON.relative_to(ROOT_PATH)), "md": str(CONTEXT_PACK_MD.relative_to(ROOT_PATH))}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "context_pack_status",
        "version": CONTEXT_PACK_VERSION,
        "json_exists": CONTEXT_PACK_JSON.exists(),
        "md_exists": CONTEXT_PACK_MD.exists(),
    }


def report() -> Dict[str, Any]:
    payload = generate()
    paths = _write_context_pack(payload)
    return {
        "ok": True,
        "mode": "context_pack_report",
        "version": CONTEXT_PACK_VERSION,
        "generated_at": _now(),
        "paths": paths,
    }


def is_context_pack_command(command: str) -> bool:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    return lowered in {
        "localcomet agent context pack",
        "agent context pack",
        "context pack",
    } or lowered.startswith("localcomet agent context pack ")


def dispatch(command: str) -> Dict[str, Any]:
    lowered = str(command or "").strip().lower().replace("\u0451", "\u0435")
    if lowered in {"localcomet agent context pack", "agent context pack", "context pack"}:
        result = report()
        return {"ok": True, "handled": True, "mode": "context_pack_generated", "version": CONTEXT_PACK_VERSION, "paths": result.get("paths", {})}
    if lowered.startswith("localcomet agent context pack "):
        result = report()
        return {"ok": True, "handled": True, "mode": "context_pack_generated", "version": CONTEXT_PACK_VERSION, "paths": result.get("paths", {})}
    if lowered in {"localcomet agent context pack status", "agent context pack status", "context pack status"}:
        return status()
    return {"ok": False, "mode": "context_pack_unknown", "version": CONTEXT_PACK_VERSION, "command": command, "hint": "Use: localcomet agent context pack"}


if __name__ == "__main__":
    result = dispatch("localcomet agent context pack")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
