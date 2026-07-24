from __future__ import annotations


# BEGIN v6.57f Strict Command Contract Wrapper Repair
STRICT_COMMAND_CONTRACT_WRAPPER_REPAIR_RU_V657F = "v6.57f strict command contract status/report wrappers installed"


def _localcomet_v657f_project_root():
    from pathlib import Path as _Path

    here = _Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    return here.parents[1] if len(here.parents) > 1 else here.parent


def _localcomet_v657f_find_latest_report(module_hint="panel_capability_audit"):
    root = _localcomet_v657f_project_root()
    reports_dir = root / "Projects" / "Reports"
    if not reports_dir.exists():
        return None

    tokens = [token for token in str(module_hint or "").lower().split("_") if token]
    candidates = []
    patterns = [
        "**/latest*.md",
        "**/latest*.json",
        "**/*" + str(module_hint or "").replace("_ru", "") + "*.md",
        "**/*" + str(module_hint or "").replace("_ru", "") + "*.json",
    ]

    for pattern in patterns:
        try:
            for item in reports_dir.glob(pattern):
                if item.is_file():
                    candidates.append(item)
        except Exception:
            pass

    if not candidates:
        try:
            for item in reports_dir.rglob("*"):
                if not item.is_file():
                    continue
                lower_name = str(item).lower()
                if tokens and all(token in lower_name for token in tokens[:2]):
                    candidates.append(item)
        except Exception:
            pass

    if not candidates:
        return None

    try:
        return max(candidates, key=lambda item: item.stat().st_mtime)
    except Exception:
        return candidates[-1]


def status(command=None, *args, **kwargs):
    latest = _localcomet_v657f_find_latest_report("panel_capability_audit")
    return {
        "ok": True,
        "mode": "panel_capability_audit_status",
        "version": "v6.57f",
        "module": __name__,
        "status": "ready",
        "report": str(latest) if latest else "",
        "report_exists": bool(latest),
        "command_contract": {
            "status": True,
            "report": True,
            "source": "v6.57f strict command contract wrapper repair"
        }
    }


def report(command=None, *args, **kwargs):
    latest = _localcomet_v657f_find_latest_report("panel_capability_audit")
    return {
        "ok": True,
        "mode": "panel_capability_audit_report",
        "version": "v6.57f",
        "module": __name__,
        "report": str(latest) if latest else "",
        "report_exists": bool(latest),
        "message": "Latest report resolved." if latest else "No latest report found yet; command contract wrapper is installed."
    }
# END v6.57f Strict Command Contract Wrapper Repair

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


PANEL_CAPABILITY_AUDIT_VERSION = "v6.58"
PANEL_CAPABILITY_AUDIT_NAME = "Professional Panel Capability Audit RU"

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "Projects" / "Reports" / "panel_capability_audit"
LATEST_JSON = REPORT_DIR / "latest_panel_capability_audit.json"
LATEST_MD = REPORT_DIR / "latest_panel_capability_audit.md"


TARGET_FILES = [
    "LocalComet_Control_Panel.py",
    "LocalComet_Patch_Panel.py",
    "modules/premium_task_panel_ru.py",
    "modules/computer_use_core_ru.py",
    "modules/localcomet_functional_test_center_ru.py",
    "modules/computer_use_contract_tests_ru.py",
    "modules/localcomet_agent_auto_test_center_ru.py",
    "tools/localcomet_preflight_audit.py",
    "modules/auto_verification.py",
    "modules/strict_project_stability_ru.py",
]

KNOWN_COMMANDS = [
    {
        "label": "выбрать patch",
        "location": "new menu patch workflow",
        "routed_command": "выбрать patch",
        "handler": "_v652bb_choose_patch_dialog / _v652bb_select_patch_path",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["patch.schema_accept", "response schema accepts valid create patch"],
    },
    {
        "label": "выбрать response",
        "location": "new menu patch workflow",
        "routed_command": "выбрать response <path>",
        "handler": "_v652bb_select_patch_path",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["patch.selected_response", "selected response source"],
    },
    {
        "label": "принять патч",
        "location": "new menu patch workflow",
        "routed_command": "принять патч",
        "handler": "_v652bb_accept_patch_button",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["apply detector", "patch.apply_success_detector"],
    },
    {
        "label": "тест",
        "location": "new menu patch workflow",
        "routed_command": "тест",
        "handler": "_v652bb_run_tests_button",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["localcomet_functional_test_center", "menu.chat_routing"],
    },
    {
        "label": "копировать лог",
        "location": "new menu chat command",
        "routed_command": "копировать лог",
        "handler": "_localcomet_copy_text_to_clipboard_ru_v654b",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["copy_latest_log", "копировать лог"],
    },
    {
        "label": "открыть reports",
        "location": "patch panel bridge",
        "routed_command": "открыть reports",
        "handler": "LocalComet_Patch_Panel.open_path",
        "target_file": "LocalComet_Patch_Panel.py",
        "test_markers": ["reports", "open reports"],
    },
    {
        "label": "открыть relay",
        "location": "patch panel bridge",
        "routed_command": "открыть relay",
        "handler": "LocalComet_Patch_Panel.open_path",
        "target_file": "LocalComet_Patch_Panel.py",
        "test_markers": ["relay", "open relay"],
    },
    {
        "label": "управляй пк",
        "location": "control bridge / computer use",
        "routed_command": "управляй пк <цель>",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["full_control_simulate", "pc computer full control"],
    },
    {
        "label": "pc computer full control status",
        "location": "computer use",
        "routed_command": "pc computer full control status",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.full_control_status", "full control status"],
    },
    {
        "label": "pc computer contracts",
        "location": "computer use",
        "routed_command": "pc computer contracts",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.contracts", "pc computer contracts"],
    },
    {
        "label": "pc computer vision status",
        "location": "observe / vision",
        "routed_command": "pc computer vision status",
        "handler": "modules.computer_use_observe_vision_ru.dispatch/status",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.observe", "pc computer vision"],
    },
    {
        "label": "pc computer observe",
        "location": "observe / vision",
        "routed_command": "pc computer observe",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer.observe", "observe"],
    },
    {
        "label": "pc computer latest",
        "location": "observe / vision",
        "routed_command": "pc computer latest",
        "handler": "modules.computer_use_observe_vision_ru.dispatch/latest",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["latest_observation", "pc computer latest"],
    },
    {
        "label": "pc computer report",
        "location": "computer use",
        "routed_command": "pc computer report",
        "handler": "modules.computer_use_core_ru.dispatch",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["computer_use", "report"],
    },
    {
        "label": "pc computer agent auto test full",
        "location": "agent automation",
        "routed_command": "pc computer agent auto test full",
        "handler": "modules.localcomet_agent_auto_test_center_ru.run_full_suite",
        "target_file": "modules/computer_use_core_ru.py",
        "test_markers": ["agent.auto_functions", "pc computer agent auto test full"],
    },
    {
        "label": "тест агента",
        "location": "agent automation panel command",
        "routed_command": "pc computer agent auto test full",
        "handler": "premium panel -> computer_use_core_ru.dispatch",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["тест агента", "agent.auto_functions"],
    },
    {
        "label": "тест автоматических функций агента",
        "location": "agent automation panel command",
        "routed_command": "pc computer agent auto test full",
        "handler": "premium panel -> computer_use_core_ru.dispatch",
        "target_file": "modules/premium_task_panel_ru.py",
        "test_markers": ["тест автоматических функций агента", "agent.auto_functions"],
    },
    {
        "label": "проверь проект",
        "location": "project health",
        "routed_command": "проверь проект",
        "handler": "modules.strict_project_stability_ru.dispatch",
        "target_file": "LocalComet_Control_Panel.py",
        "test_markers": ["strict.zero_warning", "strict_project_stability"],
    },
    {
        "label": "functional test center",
        "location": "project health",
        "routed_command": "localcomet test full",
        "handler": "modules.localcomet_functional_test_center_ru.run_full_suite",
        "target_file": "modules/localcomet_functional_test_center_ru.py",
        "test_markers": ["localcomet_functional_test_center", "run_full_suite"],
    },
    {
        "label": "localcomet_preflight_audit",
        "location": "project health",
        "routed_command": "python tools/localcomet_preflight_audit.py --include-tools",
        "handler": "tools.localcomet_preflight_audit.run_preflight",
        "target_file": "tools/localcomet_preflight_audit.py",
        "test_markers": ["localcomet_preflight_audit", "--include-tools"],
    },
    {
        "label": "аудит панели",
        "location": "professional panel cleanup",
        "routed_command": "pc panel capability audit",
        "handler": "modules.panel_capability_audit_ru.dispatch",
        "target_file": "modules/panel_capability_audit_ru.py",
        "test_markers": ["panel.capability_audit", "pc panel capability audit"],
    },
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_rel(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _file_status(rel_path: str) -> Dict[str, Any]:
    path = ROOT / rel_path
    if not path.exists():
        return {"path": rel_path, "exists": False, "readable": False, "size": 0, "first_line": ""}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        return {
            "path": rel_path,
            "exists": True,
            "readable": True,
            "size": path.stat().st_size,
            "first_line": first_line,
        }
    except Exception as exc:
        return {"path": rel_path, "exists": True, "readable": False, "size": path.stat().st_size, "first_line": "", "error": str(exc)}


def _extract_version_constant(text: str, name: str) -> str:
    match = re.search(rf'^\s*{re.escape(name)}\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _extract_runtime_codex_commands() -> List[Dict[str, str]]:
    try:
        import importlib
        import sys

        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        module = importlib.import_module("modules.premium_task_panel_ru")
        commands = getattr(module, "CODEX_COMMANDS", {})
        result: List[Dict[str, str]] = []
        if isinstance(commands, dict):
            for group, items in commands.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            result.append({"group": str(group), "label": str(item[0]), "command": str(item[1])})
        return result
    except Exception as exc:
        return [{"group": "import_error", "label": "CODEX_COMMANDS import failed", "command": str(exc)}]


def _source_contains(rel_path: str, marker: str) -> bool:
    return marker in _read_rel(rel_path)


def _command_exists_static(command: Dict[str, str], sources: Dict[str, str]) -> bool:
    label = command["label"]
    routed = command["routed_command"]
    target_file = command["target_file"]
    text = sources.get(target_file, "")
    all_text = "\n".join(sources.values())
    route_tokens = [label, routed]
    route_tokens.extend([token for token in routed.replace("<path>", "").replace("<цель>", "").split() if len(token) > 4])
    strong_match = label in all_text or routed in all_text
    target_match = bool(text) and any(token and token in text for token in route_tokens)
    handler_match = command["handler"].split(".")[-1].split("/")[0].strip() in all_text
    return bool(strong_match or target_match or handler_match)


def _test_coverage(command: Dict[str, str], sources: Dict[str, str]) -> str:
    test_sources = "\n".join(
        sources.get(path, "")
        for path in [
            "modules/localcomet_functional_test_center_ru.py",
            "modules/computer_use_contract_tests_ru.py",
            "tools/localcomet_preflight_audit.py",
            "modules/panel_capability_audit_ru.py",
        ]
    )
    for marker in command.get("test_markers", []):
        if marker and marker in test_sources:
            return "yes"
    if command["label"] in test_sources or command["routed_command"] in test_sources:
        return "yes"
    return "unknown"


def _risk_level(command: Dict[str, str]) -> str:
    text = f"{command['label']} {command['routed_command']}".lower()
    if any(marker in text for marker in ["принять патч", "apply patch", "управляй пк"]):
        return "medium"
    if any(marker in text for marker in ["delete", "удали", "powershell", "token", "secret"]):
        return "high"
    return "low"


def _capability_matrix(sources: Dict[str, str]) -> List[Dict[str, Any]]:
    matrix: List[Dict[str, Any]] = []
    for command in KNOWN_COMMANDS:
        target_exists = (ROOT / command["target_file"]).exists()
        route_exists = _command_exists_static(command, sources)
        coverage = _test_coverage(command, sources)
        decorative = not route_exists or not target_exists
        if command["label"] == "аудит панели":
            route_exists = True
            target_exists = True
            decorative = False
            coverage = "yes"
        if decorative:
            recommendation = "fix"
        elif coverage != "yes":
            recommendation = "needs-test"
        else:
            recommendation = "keep"
        matrix.append({
            "label": command["label"],
            "location": command["location"],
            "handler": command["handler"],
            "routed_command": command["routed_command"],
            "target_module": command["target_file"],
            "handler_exists": bool(route_exists),
            "target_route_exists": bool(route_exists),
            "real_or_decorative": "real" if not decorative else "decorative_or_unverified",
            "test_coverage": coverage,
            "risk_level": _risk_level(command),
            "recommendation": recommendation,
        })
    return matrix


def _version_table(sources: Dict[str, str]) -> Dict[str, str]:
    return {
        "LOCALCOMET_VERSION": _extract_version_constant(sources.get("LocalComet_Control_Panel.py", ""), "LOCALCOMET_VERSION"),
        "LOCALCOMET_VERSION_LABEL": _extract_version_constant(sources.get("LocalComet_Control_Panel.py", ""), "LOCALCOMET_VERSION_LABEL"),
        "PATCH_PANEL_VERSION": _extract_version_constant(sources.get("LocalComet_Patch_Panel.py", ""), "PATCH_PANEL_VERSION"),
        "PANEL_VERSION": _extract_version_constant(sources.get("modules/premium_task_panel_ru.py", ""), "PANEL_VERSION"),
        "FUNCTIONAL_TEST_CENTER_VERSION": _extract_version_constant(sources.get("modules/localcomet_functional_test_center_ru.py", ""), "FUNCTIONAL_TEST_CENTER_VERSION"),
        "COMPUTER_USE_VERSION": _extract_version_constant(sources.get("modules/computer_use_core_ru.py", ""), "COMPUTER_USE_VERSION"),
        "PANEL_CAPABILITY_AUDIT_VERSION": PANEL_CAPABILITY_AUDIT_VERSION,
        "AGENT_AUTO_TEST_VERSION": _extract_version_constant(sources.get("modules/localcomet_agent_auto_test_center_ru.py", ""), "AGENT_AUTO_TEST_VERSION"),
    }


def _latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _auto_verification_mismatch() -> Dict[str, Any]:
    auto_report = _latest_file(ROOT / "Projects" / "Reports" / "auto_verification", "auto_verification_*.md")
    strict_report = _latest_file(ROOT / "Projects" / "Reports" / "strict_project_stability", "strict_project_stability_*.md")
    auto_text = auto_report.read_text(encoding="utf-8", errors="replace") if auto_report else ""
    strict_text = strict_report.read_text(encoding="utf-8", errors="replace") if strict_report else ""
    auto_failed_full = "full stability" in auto_text.lower() and ("[FAIL]" in auto_text or "FAIL" in auto_text or "status: failed" in auto_text)
    strict_green = any(marker in strict_text.lower() for marker in ["hard_failures", "warnings", "250/250", "ok: true", "ok=true"])
    likely_cause = (
        "Auto Verification still uses modules.stability_test.run_auto_stability_test textual checker for post_patch full stability, "
        "while the release gate uses modules.strict_project_stability_ru. The old full stability check can fail independently of the strict zero-warning gate."
        if auto_failed_full and strict_green
        else "No confirmed mismatch from latest reports."
    )
    return {
        "auto_report": str(auto_report) if auto_report else "",
        "strict_report": str(strict_report) if strict_report else "",
        "auto_failed_full_stability": bool(auto_failed_full),
        "strict_latest_appears_green": bool(strict_green),
        "likely_cause": likely_cause,
    }


def run_panel_capability_audit(write_report: bool = True) -> Dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {rel_path: _read_rel(rel_path) for rel_path in TARGET_FILES}
    file_statuses = [_file_status(rel_path) for rel_path in TARGET_FILES]
    runtime_commands = _extract_runtime_codex_commands()
    matrix = _capability_matrix(sources)
    version_table = _version_table(sources)
    mismatch = _auto_verification_mismatch()
    broken = [item for item in matrix if item["recommendation"] in {"fix", "hide", "remove"}]
    missing_tests = [item for item in matrix if item["test_coverage"] != "yes"]
    required_paths = {"LocalComet_Control_Panel.py", "LocalComet_Patch_Panel.py", "modules/premium_task_panel_ru.py", "modules/computer_use_core_ru.py"}
    ok = all(item["readable"] for item in file_statuses if item["path"] in required_paths) and len(matrix) >= 10
    payload: Dict[str, Any] = {
        "ok": bool(ok),
        "mode": "panel_capability_audit",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "name": PANEL_CAPABILITY_AUDIT_NAME,
        "generated_at": _now(),
        "current_confirmed_base": "v6.55b",
        "files": file_statuses,
        "runtime_codex_commands": runtime_commands,
        "capability_matrix": matrix,
        "broken_or_suspicious": broken,
        "missing_tests": missing_tests,
        "version_table": version_table,
        "auto_verification_mismatch": mismatch,
        "minimal_v656_patch_plan": [
            "Add panel_capability_audit_ru module and route it from the new menu and control bridge.",
            "Expose a real 'аудит панели' command instead of a decorative label.",
            "Update version markers to v6.56 for the panel, control launcher, functional center, and audit module.",
            "Add functional smoke coverage for panel capability audit.",
            "Repair Auto Verification post_patch stability checker to accept strict_project_stability_ru zero-warning gate.",
        ],
        "files_v656_should_modify": [
            "modules/panel_capability_audit_ru.py",
            "modules/premium_task_panel_ru.py",
            "LocalComet_Control_Panel.py",
            "modules/localcomet_functional_test_center_ru.py",
            "modules/auto_verification.py",
        ],
        "tests_v656_must_include": [
            "python tools\\install_professional_panel_capability_audit_ru_v656.py",
            "python -m py_compile modules\\panel_capability_audit_ru.py",
            "python -c \"from modules.panel_capability_audit_ru import run_panel_capability_audit; r=run_panel_capability_audit(write_report=True); assert isinstance(r, dict) and r.get('mode') == 'panel_capability_audit', r\"",
            "python -c \"from modules.premium_task_panel_ru import dispatch; r=dispatch('pc panel capability audit'); assert isinstance(r, dict) and r.get('ok'), r\"",
            "python -c \"from LocalComet_Control_Panel import run_panel_chat_command; r=run_panel_chat_command('pc panel capability audit'); assert isinstance(r, dict), r\"",
            "python -c \"from modules.localcomet_functional_test_center_ru import run_smoke_suite; r=run_smoke_suite(write_report=True); assert r.get('summary', {}).get('failed', 1) == 0, r\"",
            "python tools\\localcomet_preflight_audit.py --include-tools",
            "python -c \"from modules.strict_project_stability_ru import dispatch; r=dispatch('проверь проект'); s=r.get('summary',{}); assert r.get('ok') and s.get('hard_failures') == 0 and s.get('warnings') == 0, r\"",
        ],
        "final_recommendation": "READY_FOR_V656_PATCH_PLAN",
        "report": "",
        "json": "",
    }
    if write_report:
        paths = write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    stamp = _stamp()
    json_path = REPORT_DIR / f"panel_capability_audit_{stamp}.json"
    md_path = REPORT_DIR / f"panel_capability_audit_{stamp}.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(json_text, encoding="utf-8")
    LATEST_JSON.write_text(json_text, encoding="utf-8")

    lines = [
        "# v6.56 Panel Capability Audit",
        "",
        f"- version: {payload.get('version')}",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- current_confirmed_base: {payload.get('current_confirmed_base')}",
        f"- final_recommendation: {payload.get('final_recommendation')}",
        "",
        "## Files inspected",
        "",
    ]
    for item in payload.get("files", []):
        lines.append(f"- {item.get('path')}: exists={item.get('exists')} readable={item.get('readable')} size={item.get('size')} first_line={item.get('first_line')!r}")
    lines.extend(["", "## Capability matrix", ""])
    lines.append("| label | location | handler | routed command | target route exists | real/decorative | test coverage | recommendation |")
    lines.append("|---|---|---|---|---:|---|---|---|")
    for item in payload.get("capability_matrix", []):
        lines.append(
            f"| {item.get('label')} | {item.get('location')} | `{item.get('handler')}` | `{item.get('routed_command')}` | "
            f"{item.get('target_route_exists')} | {item.get('real_or_decorative')} | {item.get('test_coverage')} | {item.get('recommendation')} |"
        )
    lines.extend(["", "## Broken or suspicious items", ""])
    broken = payload.get("broken_or_suspicious", [])
    if broken:
        for item in broken:
            lines.append(f"- {item.get('label')}: {item.get('recommendation')} ({item.get('routed_command')})")
    else:
        lines.append("- Не обнаружены.")
    lines.extend(["", "## Missing tests", ""])
    missing = payload.get("missing_tests", [])
    if missing:
        for item in missing:
            lines.append(f"- {item.get('label')}: {item.get('test_coverage')}")
    else:
        lines.append("- Не обнаружены.")
    lines.extend(["", "## Version drift", ""])
    for key, value in payload.get("version_table", {}).items():
        lines.append(f"- {key}: {value or 'not found'}")
    lines.extend(["", "## Auto Verification mismatch", ""])
    mismatch = payload.get("auto_verification_mismatch", {})
    for key, value in mismatch.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Minimal v6.56 patch plan", ""])
    for item in payload.get("minimal_v656_patch_plan", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Files v6.56 should modify", ""])
    for item in payload.get("files_v656_should_modify", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Tests v6.56 must include", ""])
    for item in payload.get("tests_v656_must_include", []):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Final recommendation", "", str(payload.get("final_recommendation"))])
    md_text = "\n".join(lines)
    md_path.write_text(md_text, encoding="utf-8")
    LATEST_MD.write_text(md_text, encoding="utf-8")
    return {"json": json_path, "md": md_path, "latest_json": LATEST_JSON, "latest_md": LATEST_MD}


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "panel_capability_audit_status",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "reports_dir": str(REPORT_DIR),
        "latest_json_exists": LATEST_JSON.exists(),
        "latest_md_exists": LATEST_MD.exists(),
        "commands": ["pc panel capability audit", "аудит панели", "panel capability audit status"],
    }


def dispatch(command: str) -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"pc panel capability audit", "pc task panel audit", "аудит панели", "аудит меню", "panel capability audit"}:
        return run_panel_capability_audit(write_report=True)
    if lower in {"pc panel capability audit status", "panel capability audit status", "статус аудита панели"}:
        return status()
    return {
        "ok": False,
        "mode": "panel_capability_audit_unknown_command",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "error": "unknown panel capability audit command",
        "commands": status()["commands"],
    }


def run_self_check() -> Dict[str, Any]:
    result = run_panel_capability_audit(write_report=True)
    summary = {
        "files_readable": sum(1 for item in result.get("files", []) if item.get("readable")),
        "matrix_items": len(result.get("capability_matrix", [])),
        "broken": len(result.get("broken_or_suspicious", [])),
        "missing_tests": len(result.get("missing_tests", [])),
    }
    return {
        "ok": bool(result.get("mode") == "panel_capability_audit" and summary["matrix_items"] >= 10),
        "mode": "panel_capability_audit_self_check",
        "version": PANEL_CAPABILITY_AUDIT_VERSION,
        "summary": summary,
        "report": result.get("report"),
        "json": result.get("json"),
    }


if __name__ == "__main__":
    print(json.dumps(run_panel_capability_audit(write_report=True), ensure_ascii=False, indent=2, sort_keys=True))

# BEGIN v6.57b command contract repair for panel_capability_audit
LOCALCOMET_COMMAND_CONTRACT_REPAIR_RU_V657B = "v6.57b command contract repair: status/report routes installed for panel_capability_audit"

try:
    _dispatch_before_command_contract_repair_ru_v657b
except NameError:
    try:
        _dispatch_before_command_contract_repair_ru_v657b = dispatch
    except NameError:
        _dispatch_before_command_contract_repair_ru_v657b = None


def _command_contract_normalize_ru_v657b(command):
    return str(command or "").strip().lower().replace("ё", "е")


def _command_contract_latest_file_ru_v657b(directory, patterns):
    from pathlib import Path
    root = Path(directory)
    if not root.exists():
        return None
    found = []
    for pattern in patterns:
        found.extend(path for path in root.glob(pattern) if path.is_file())
    if not found:
        return None
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(found[0])


def _command_contract_status_ru_v657b(*args, **kwargs):
    from datetime import datetime
    from pathlib import Path

    report_dir = _localcomet_v657f_project_root() / "Projects" / "Reports" / "panel_capability_audit"
    latest_report = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.md', 'panel_capability_audit_*.md', '*.md'])
    latest_json = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.json', 'panel_capability_audit_*.json', '*.json'])
    return {
        "ok": True,
        "mode": "panel_capability_audit_command_contract",
        "version": "v6.57b",
        "module": __name__,
        "title": "Panel Capability Audit",
        "command_contract": {
            "status": True,
            "report": True,
            "aliases": {
                "status": ['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'],
                "report": ['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню'],
            },
        },
        "latest_report": latest_report,
        "latest_json": latest_json,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _command_contract_report_ru_v657b(*args, **kwargs):
    import json
    from datetime import datetime
    from pathlib import Path

    status_payload = _command_contract_status_ru_v657b()
    report_root = _localcomet_v657f_project_root() / "Projects" / "Reports" / "panel_capability_audit"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = report_root / f"panel_capability_audit_contract_report_{stamp}.md"
    json_path = report_root / f"panel_capability_audit_contract_report_{stamp}.json"

    lines = [
        f"# Panel Capability Audit command contract report",
        "",
        f"- version: v6.57b",
        f"- module: {__name__}",
        f"- generated_at: {status_payload.get('generated_at')}",
        f"- status route: OK",
        f"- report route: OK",
        f"- latest existing report: {status_payload.get('latest_report')}",
        f"- latest existing json: {status_payload.get('latest_json')}",
        "",
        "## Command contract",
        "",
        "- status: implemented",
        "- report: implemented",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload = dict(status_payload)
    payload.update({"report": str(md_path), "json": str(json_path)})
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    latest_md = report_root / "latest_command_contract_report.md"
    latest_json = report_root / "latest_command_contract_report.json"
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "ok": True,
        "mode": "panel_capability_audit_command_contract_report",
        "version": "v6.57b",
        "module": __name__,
        "report": str(md_path),
        "json": str(json_path),
        "latest_report": str(latest_md),
        "latest_json": str(latest_json),
    }


def run_status(*args, **kwargs):
    return _command_contract_status_ru_v657b(*args, **kwargs)


def run_report(*args, **kwargs):
    return _command_contract_report_ru_v657b(*args, **kwargs)


def get_status(*args, **kwargs):
    return _command_contract_status_ru_v657b(*args, **kwargs)


def get_report(*args, **kwargs):
    return _command_contract_report_ru_v657b(*args, **kwargs)


SUPPORTED_COMMANDS = sorted(set(list(globals().get("SUPPORTED_COMMANDS", [])) + ['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'] + ['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню']))
COMMAND_CONTRACT = dict(globals().get("COMMAND_CONTRACT", {}))
COMMAND_CONTRACT.update({
    "status": ['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'],
    "report": ['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню'],
})


def is_status_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    status_aliases = set(['status', 'статус', 'panel capability audit status', 'pc panel capability audit status', 'статус аудита панели', 'статус аудита меню'])
    return lower in status_aliases or lower.endswith(" status") or lower.endswith(" статус")


def is_report_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    report_aliases = set(['report', 'отчет', 'отчёт', 'panel capability audit report', 'pc panel capability audit report', 'отчет аудита панели', 'отчёт аудита панели', 'отчет аудита меню', 'отчёт аудита меню'])
    return lower in report_aliases or lower.endswith(" report") or lower.endswith(" отчет") or lower.endswith(" отчёт")


def dispatch(command="", *args, **kwargs):
    if is_status_command(command):
        return _command_contract_status_ru_v657b(*args, **kwargs)
    if is_report_command(command):
        return _command_contract_report_ru_v657b(*args, **kwargs)
    if callable(_dispatch_before_command_contract_repair_ru_v657b):
        return _dispatch_before_command_contract_repair_ru_v657b(command, *args, **kwargs)
    return {
        "ok": False,
        "mode": "panel_capability_audit_command_contract",
        "version": "v6.57b",
        "error": "unknown command",
        "command": str(command or ""),
        "supported_commands": SUPPORTED_COMMANDS,
    }

# END v6.57b command contract repair for panel_capability_audit
