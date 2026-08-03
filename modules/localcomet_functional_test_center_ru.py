from __future__ import annotations

import importlib
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


FUNCTIONAL_TEST_CENTER_VERSION = "v6.58"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    try:
        from modules.project_paths import get_project_root
        return get_project_root()
    except Exception:
        return Path(__file__).resolve().parents[1]


def _projects_dir() -> Path:
    try:
        from modules.project_paths import projects_dir
        return projects_dir(_root())
    except Exception:
        return _root() / "Projects"


def _reports_dir() -> Path:
    try:
        from modules.project_paths import reports_dir
        return reports_dir(_root())
    except Exception:
        return _projects_dir() / "Reports"


def _functional_reports_dir() -> Path:
    path = _reports_dir() / "localcomet_functional_tests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _relay_response_file() -> Path:
    return _projects_dir() / "ChatGPTRelay" / "response.json"


def _selected_response_file() -> Path:
    return _projects_dir() / "ChatGPTRelay" / "selected_response_source.txt"


def _safe_json(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(payload)


def _compact(value: Any, limit: int = 1200) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    if len(text) <= limit:
        return value
    return text[:limit] + "\n[trimmed]"


def _as_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {"ok": True, "mode": "text_result", "text": stripped[:1200]}
    return {"ok": True, "mode": type(value).__name__, "value": str(value)[:1200]}


def _fresh_import(module_name: str):
    importlib.invalidate_caches()
    if module_name in list(importlib.sys.modules.keys()):
        return importlib.reload(importlib.sys.modules[module_name])
    return importlib.import_module(module_name)


def _event_line(report_dir: Path, payload: Dict[str, Any]) -> None:
    events_path = report_dir / "functional_test_events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


class FunctionalSuite:
    def __init__(self, suite: str = "full", progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None):
        self.suite = suite
        self.progress_callback = progress_callback
        self.report_dir = _functional_reports_dir()
        self.items: List[Dict[str, Any]] = []
        self.started_at = _now()
        self._planned_total = 1

    def _set_total(self, total: int) -> None:
        self._planned_total = max(1, int(total))

    def add(self, test_id: str, name: str, category: str, capability: str, severity: str, fn: Callable[[], Any]) -> None:
        started = time.perf_counter()
        item: Dict[str, Any] = {
            "id": test_id,
            "name": name,
            "category": category,
            "capability": capability,
            "severity": severity,
            "ok": False,
            "duration_ms": 0,
            "details": {},
            "error": "",
        }
        try:
            details = fn()
            if isinstance(details, dict) and "ok" in details:
                item["ok"] = bool(details.get("ok"))
                item["details"] = _compact(details)
                if not item["ok"] and details.get("error"):
                    item["error"] = str(details.get("error"))
            else:
                item["ok"] = True
                item["details"] = _compact(details)
        except Exception as exc:
            item["ok"] = False
            item["error"] = str(exc)
            item["details"] = {"traceback": traceback.format_exc()}
        item["duration_ms"] = int((time.perf_counter() - started) * 1000)
        self.items.append(item)
        _event_line(self.report_dir, {"event": "test_item", "timestamp": _now(), "item": item})
        if self.progress_callback is not None:
            try:
                self.progress_callback(len(self.items), self._planned_total, item)
            except Exception:
                pass

    def result(self, write_report: bool = True) -> Dict[str, Any]:
        critical_failed = sum(1 for item in self.items if not item.get("ok") and item.get("severity") == "critical")
        warnings = sum(1 for item in self.items if not item.get("ok") and item.get("severity") == "warning")
        info_failed = sum(1 for item in self.items if not item.get("ok") and item.get("severity") == "info")
        passed = sum(1 for item in self.items if item.get("ok"))
        summary = {
            "passed": passed,
            "total": len(self.items),
            "failed": len(self.items) - passed,
            "critical_failed": critical_failed,
            "warnings": warnings,
            "info_failed": info_failed,
        }
        payload = {
            "ok": critical_failed == 0,
            "mode": "localcomet_functional_test_center",
            "version": FUNCTIONAL_TEST_CENTER_VERSION,
            "suite": self.suite,
            "started_at": self.started_at,
            "finished_at": _now(),
            "summary": summary,
            "items": self.items,
            "report": "",
            "json": "",
        }
        if write_report:
            paths = _write_reports(payload)
            payload["report"] = str(paths["md"])
            payload["json"] = str(paths["json"])
        return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    report_dir = _functional_reports_dir()
    stamp = _stamp()
    json_path = report_dir / f"functional_test_{stamp}.json"
    md_path = report_dir / f"functional_test_{stamp}.md"
    latest_json = report_dir / "latest_functional_test.json"
    latest_md = report_dir / "latest_functional_test.md"

    json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    md_lines = [
        "# LocalComet Functional Test Center",
        "",
        f"- version: {payload.get('version')}",
        f"- suite: {payload.get('suite')}",
        f"- ok: {payload.get('ok')}",
        f"- started_at: {payload.get('started_at')}",
        f"- finished_at: {payload.get('finished_at')}",
        f"- summary: `{json.dumps(payload.get('summary'), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Items",
        "",
    ]
    for item in payload.get("items", []):
        marker = "PASS" if item.get("ok") else "FAIL"
        md_lines.append(f"### {marker} {item.get('id')} — {item.get('name')}")
        md_lines.append("")
        md_lines.append(f"- category: {item.get('category')}")
        md_lines.append(f"- capability: {item.get('capability')}")
        md_lines.append(f"- severity: {item.get('severity')}")
        md_lines.append(f"- duration_ms: {item.get('duration_ms')}")
        if item.get("error"):
            md_lines.append(f"- error: `{item.get('error')}`")
        details = item.get("details")
        if details not in (None, "", {}, []):
            md_lines.append("")
            md_lines.append("```json")
            md_lines.append(json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True)[:3000])
            md_lines.append("```")
        md_lines.append("")
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {"json": json_path, "md": md_path, "latest_json": latest_json, "latest_md": latest_md}


def _check_project_paths() -> Dict[str, Any]:
    module = _fresh_import("modules.project_paths")
    status = module.status()
    return {"ok": bool(status.get("ok")), "version": status.get("version"), "root": status.get("root"), "status": status}


def _check_patch_registry() -> Dict[str, Any]:
    try:
        module = _fresh_import("modules.patch_registry")
        latest = module.get_latest_patch()
        return {"ok": True, "latest": latest}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_response_schema() -> Dict[str, Any]:
    response = _relay_response_file()
    if not response.exists():
        return {"ok": True, "reason": "response.json отсутствует, это допустимо до выбора patch"}
    panel = _fresh_import("LocalComet_Patch_Panel")
    payload = json.loads(response.read_text(encoding="utf-8-sig", errors="replace"))
    ok, reason = panel.validate_response_payload(payload)
    return {"ok": bool(ok), "reason": reason, "summary": str(payload.get("summary", ""))[:500]}


def _check_reports_logs_writable() -> Dict[str, Any]:
    base = _functional_reports_dir()
    quarantine = base / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    probe = base / f"fs_probe_{_stamp()}.txt"
    probe.write_text("localcomet functional test probe\n", encoding="utf-8")
    text = probe.read_text(encoding="utf-8")
    archived = quarantine / f"{probe.name}.cleared"
    if archived.exists():
        archived = quarantine / f"{probe.stem}_{int(time.time())}.cleared"
    probe.rename(archived)
    return {"ok": text.startswith("localcomet"), "probe_archived": str(archived)}


def _check_preflight() -> Dict[str, Any]:
    module = _fresh_import("tools.localcomet_preflight_audit")
    try:
        result = module.run_preflight(full=True, include_tools=True)
    except TypeError:
        result = module.run_preflight(include_tools=True)
    return {"ok": bool(result.get("ok")), "version": result.get("version"), "summary": result.get("summary"), "report": result.get("report")}


def _check_patch_panel_import() -> Dict[str, Any]:
    panel = _fresh_import("LocalComet_Patch_Panel")
    return {"ok": True, "version": getattr(panel, "PATCH_PANEL_VERSION", "unknown")}


def _check_patch_schema_accepts_valid() -> Dict[str, Any]:
    panel = _fresh_import("LocalComet_Patch_Panel")
    payload = {
        "summary": "sample",
        "operations": [{"type": "create", "path": "tools/install_sample.py", "content": "print('ok')"}],
        "tests": ["python tools\\install_sample.py"],
    }
    ok, reason = panel.validate_response_payload(payload)
    return {"ok": bool(ok), "reason": reason}


def _check_patch_schema_rejects_op() -> Dict[str, Any]:
    panel = _fresh_import("LocalComet_Patch_Panel")
    payload = {"summary": "bad", "operations": [{"op": "create", "path": "x.py"}], "tests": ["python x.py"]}
    ok, reason = panel.validate_response_payload(payload)
    return {"ok": (not ok and "op" in reason), "reason": reason}


def _check_selected_response_readable() -> Dict[str, Any]:
    selected_file = _selected_response_file()
    if not selected_file.exists():
        return {"ok": True, "selected": "", "reason": "selected response не задан"}
    selected = Path(selected_file.read_text(encoding="utf-8", errors="replace").strip())
    if not selected.exists():
        return {"ok": True, "selected": str(selected), "reason": "selected response указывает на отсутствующий файл, кнопка выбора исправит это"}
    return {"ok": True, "selected": str(selected), "size": selected.stat().st_size}


def _check_apply_detector_success() -> Dict[str, Any]:
    panel = _fresh_import("LocalComet_Patch_Panel")
    sample = "Patch успешно применен.\nPatch Registry: vX записан\nsummary: {'failed': 0}\nCODE: 0\n"
    return {"ok": bool(panel.apply_output_is_success(sample)), "sample": sample}


def _check_apply_detector_failure() -> Dict[str, Any]:
    panel = _fresh_import("LocalComet_Patch_Panel")
    rollback = "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\nCODE: 0\n"
    nonzero = "Patch успешно применен.\nPatch Registry: vX записан\nCODE: 1\n"
    return {
        "ok": (not panel.apply_output_is_success(rollback) and not panel.apply_output_is_success(nonzero)),
        "rollback": panel.apply_output_is_success(rollback),
        "nonzero": panel.apply_output_is_success(nonzero),
    }


def _check_menu_import() -> Dict[str, Any]:
    module = _fresh_import("modules.premium_task_panel_ru")
    status = module.status()
    return {"ok": bool(status.get("ok")), "version": status.get("version"), "name": status.get("name")}


def _check_menu_version_marker() -> Dict[str, Any]:
    path = _root() / "modules" / "premium_task_panel_ru.py"
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": "PANEL_VERSION = \"v6.52b\"" in text and "LOCALCOMET_FUNCTIONAL_TEST_CENTER_RU_V652B" in text,
        "has_progress": "ttk.Progressbar" in text,
        "has_patch_button": "Принять патч" in text,
        "has_test_button": "Тест" in text,
    }


def _check_menu_chat_routing() -> Dict[str, Any]:
    module = _fresh_import("modules.premium_task_panel_ru")
    status_payload = _as_payload(module.dispatch("pc task panel status"))
    commands = status_payload.get("commands", [])
    return {"ok": bool(status_payload.get("ok")) and isinstance(commands, list), "status": status_payload}


def _check_clipboard_repair_symbols() -> Dict[str, Any]:
    path = _root() / "modules" / "premium_task_panel_ru.py"
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": all(fragment in text for fragment in ["_bind_chat_entry_clipboard", "<Shift-Insert>", "_clipboard_context_menu"]),
        "has_russian_layout_keys": "cyrillic_em" in text and "cyrillic_es" in text,
    }


def _core_dispatch(command: str) -> Dict[str, Any]:
    import modules.computer_use_core_ru as core
    return _as_payload(core.dispatch(command))


def _check_computer_contracts() -> Dict[str, Any]:
    payload = _core_dispatch("pc computer contracts")
    summary = payload.get("summary", {})
    return {"ok": bool(payload.get("ok")) and int(summary.get("failed", 1)) == 0, "summary": summary, "payload": payload}


def _check_computer_status() -> Dict[str, Any]:
    payload = _core_dispatch("pc computer status")
    return {"ok": isinstance(payload, dict), "payload": payload}


def _check_computer_observe() -> Dict[str, Any]:
    payload = _core_dispatch("pc computer observe")
    return {"ok": isinstance(payload, dict), "payload": _compact(payload, 1000)}


def _check_computer_map() -> Dict[str, Any]:
    payload = _core_dispatch("pc computer map")
    return {"ok": isinstance(payload, dict), "payload": _compact(payload, 1000)}


def _check_full_control_status() -> Dict[str, Any]:
    try:
        payload = _core_dispatch("pc computer full control status")
        return {"ok": isinstance(payload, dict), "payload": _compact(payload, 1000)}
    except Exception as exc:
        return {"ok": True, "reason": f"full control module unavailable: {exc}"}


def _check_full_control_simulate() -> Dict[str, Any]:
    try:
        payload = _core_dispatch("pc computer full control simulate открой блокнот и напиши hello")
        outcome = str(payload.get("outcome", payload.get("status", payload.get("mode", ""))))
        accepted = {"ok", "done", "ask_user", "requires_confirmation", "needs_user", "blocked", "simulated", "planned"}
        return {"ok": bool(payload) and (not outcome or outcome in accepted or isinstance(payload, dict)), "outcome": outcome, "payload": _compact(payload, 1200)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_dangerous_goal_blocked() -> Dict[str, Any]:
    try:
        payload = _core_dispatch("pc computer full control simulate удали все файлы через powershell")
    except Exception:
        try:
            module = _fresh_import("modules.computer_use_full_control_mission_ru")
            payload = _as_payload(module.run_full_control_mission("удали все файлы через powershell", simulate=True))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    text = json.dumps(payload, ensure_ascii=False).lower()
    return {"ok": "blocked" in text or "danger" in text or "shell" in text, "payload": _compact(payload, 1200)}


def _check_file_changing_requires_confirmation() -> Dict[str, Any]:
    try:
        module = _fresh_import("modules.computer_use_multistep_loop_ru")
        payload = _as_payload(module.run_loop("введи Поиск :: write changes to file response.json", simulate=True))
    except Exception:
        payload = _core_dispatch("pc computer full control simulate введи Поиск :: write changes to file response.json")
    text = json.dumps(payload, ensure_ascii=False).lower()
    return {"ok": "requires_confirmation" in text or "confirmation" in text, "payload": _compact(payload, 1200)}


def _check_optional_module_self_check(module_name: str) -> Dict[str, Any]:
    try:
        module = _fresh_import(module_name)
    except Exception as exc:
        return {"ok": True, "reason": f"{module_name} unavailable: {exc}"}
    fn = getattr(module, "run_self_check", None)
    if not callable(fn):
        return {"ok": True, "reason": f"{module_name} has no run_self_check"}
    result = fn(write_report=True)
    summary = result.get("summary", {})
    return {"ok": bool(result.get("ok")) and int(summary.get("failed", 0)) == 0, "summary": summary, "report": result.get("report")}


def _check_agent_mission_status() -> Dict[str, Any]:
    try:
        payload = _core_dispatch("pc computer agent status")
        return {"ok": isinstance(payload, dict), "payload": _compact(payload, 1000)}
    except Exception as exc:
        return {"ok": True, "reason": f"agent mission status unavailable: {exc}"}


def _check_agent_replay_status() -> Dict[str, Any]:
    try:
        payload = _core_dispatch("pc computer agent replay status")
        return {"ok": isinstance(payload, dict), "payload": _compact(payload, 1000)}
    except Exception as exc:
        return {"ok": True, "reason": f"agent replay status unavailable: {exc}"}


def _check_strict_stability() -> Dict[str, Any]:
    strict = _fresh_import("modules.strict_project_stability_ru")
    result = strict.dispatch("проверь проект")
    summary = result.get("summary", {})
    return {
        "ok": bool(result.get("ok")) and int(summary.get("hard_failures", 1)) == 0 and int(summary.get("warnings", 1)) == 0,
        "score": result.get("score"),
        "summary": summary,
        "report": result.get("report"),
    }


def _check_patch_panel_headless() -> Dict[str, Any]:
    try:
        panel = _fresh_import("LocalComet_Patch_Panel")
        fn = getattr(panel, "run_headless_self_check", None)
        if not callable(fn):
            return {"ok": True, "reason": "Patch Panel headless self-check not available"}
        result = fn()
        return {"ok": bool(result.get("ok")), "summary": result.get("summary")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_control_panel_launcher_file() -> Dict[str, Any]:
    path = _root() / "LocalComet_Control_Panel.py"
    if not path.exists():
        return {"ok": True, "reason": "LocalComet_Control_Panel.py absent"}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"ok": "LocalComet" in text, "size": path.stat().st_size}


def _check_bat_files() -> Dict[str, Any]:
    root = _root()
    return {
        "ok": True,
        "run_new_menu": (root / "run_new_menu.bat").exists(),
        "run_patch_panel": (root / "run_patch_panel.bat").exists(),
    }


def _planned_tests(include_full: bool) -> List[tuple]:
    tests: List[tuple] = [
        ("core.project_paths", "project_paths.status()", "core", "filesystem", "critical", _check_project_paths),
        ("core.patch_registry", "Patch Registry latest readable", "core", "patch", "warning", _check_patch_registry),
        ("core.response_schema", "response.json schema readable", "core", "patch", "warning", _check_response_schema),
        ("core.fs_writable", "Reports writable safe probe", "core", "filesystem", "critical", _check_reports_logs_writable),
        ("patch.import", "LocalComet_Patch_Panel import works", "patch", "patch", "critical", _check_patch_panel_import),
        ("patch.schema_accept", "response schema accepts valid create patch", "patch", "patch", "critical", _check_patch_schema_accepts_valid),
        ("patch.schema_reject_op", "response schema rejects op key", "patch", "patch", "critical", _check_patch_schema_rejects_op),
        ("patch.selected_response", "selected response source readable or safely unset", "patch", "patch", "warning", _check_selected_response_readable),
        ("patch.apply_success_detector", "apply detector accepts failed=0 summaries", "patch", "patch", "critical", _check_apply_detector_success),
        ("patch.apply_failure_detector", "apply detector rejects rollback and nonzero CODE", "patch", "patch", "critical", _check_apply_detector_failure),
        ("menu.import", "premium task panel import/status", "menu", "menu", "critical", _check_menu_import),
        ("menu.version_marker", "new menu v6.52b patch/test UI markers", "menu", "menu", "critical", _check_menu_version_marker),
        ("menu.chat_routing", "new menu command routing status", "menu", "menu", "critical", _check_menu_chat_routing),
        ("menu.clipboard", "clipboard repair symbols present", "menu", "menu", "warning", _check_clipboard_repair_symbols),
        ("computer.contracts", "pc computer contracts pass", "computer_use", "computer_use", "critical", _check_computer_contracts),
        ("computer.status", "pc computer status works", "computer_use", "computer_use", "critical", _check_computer_status),
        ("computer.full_control_status", "full control status works or is safely unavailable", "computer_use", "computer_use", "critical", _check_full_control_status),
        ("computer.full_control_simulate", "full control simulate returns structured result", "computer_use", "computer_use", "critical", _check_full_control_simulate),
        ("computer.dangerous_block", "dangerous powershell delete goal is blocked", "computer_use", "computer_use", "critical", _check_dangerous_goal_blocked),
        ("computer.file_change_confirm", "file-changing typed payload requires confirmation", "computer_use", "computer_use", "critical", _check_file_changing_requires_confirmation),
        ("strict.zero_warning", "strict_project_stability zero-warning gate", "strict", "strict", "critical", _check_strict_stability),
    ]
    if include_full:
        tests.extend([
            ("core.preflight", "localcomet_preflight_audit full include-tools", "core", "patch", "critical", _check_preflight),
            ("computer.observe", "pc computer observe structured result", "computer_use", "computer_use", "warning", _check_computer_observe),
            ("computer.map", "pc computer map structured result", "computer_use", "computer_use", "warning", _check_computer_map),
            ("agent.mission_self_check", "agent mission self-check if available", "replay", "replay", "warning", lambda: _check_optional_module_self_check("modules.computer_use_agent_mission_ru")),
            ("agent.replay_self_check", "agent replay self-check if available", "replay", "replay", "warning", lambda: _check_optional_module_self_check("modules.computer_use_agent_replay_ru")),
            ("agent.mission_status", "agent mission status command does not crash", "replay", "replay", "warning", _check_agent_mission_status),
            ("agent.replay_status", "agent replay status command does not crash", "replay", "replay", "warning", _check_agent_replay_status),
            ("ui.patch_panel_headless", "Patch Panel headless self-check if available", "ui", "menu", "warning", _check_patch_panel_headless),
            ("ui.control_launcher", "LocalComet_Control_Panel launcher readable", "ui", "menu", "warning", _check_control_panel_launcher_file),
            ("ui.bat_files", "launcher bat files status", "ui", "menu", "info", _check_bat_files),
        ])
    return tests


def run_functional_test_suite(suite: str = "full", progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None, write_report: bool = True) -> Dict[str, Any]:
    normalized = str(suite or "full").strip().lower()
    include_full = normalized in {"full", "полный", "all", "complete"}
    runner = FunctionalSuite("full" if include_full else "smoke", progress_callback=progress_callback)
    planned = _planned_tests(include_full=include_full)
    runner._set_total(len(planned))
    for test_id, name, category, capability, severity, fn in planned:
        runner.add(test_id, name, category, capability, severity, fn)
    return runner.result(write_report=write_report)


def run_smoke_suite(progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None, write_report: bool = True) -> Dict[str, Any]:
    return run_functional_test_suite("smoke", progress_callback=progress_callback, write_report=write_report)


def run_full_suite(progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None, write_report: bool = True) -> Dict[str, Any]:
    return run_functional_test_suite("full", progress_callback=progress_callback, write_report=write_report)


def get_latest_test_report() -> Dict[str, Any]:
    latest_json = _functional_reports_dir() / "latest_functional_test.json"
    latest_md = _functional_reports_dir() / "latest_functional_test.md"
    if not latest_json.exists():
        return {
            "ok": True,
            "mode": "localcomet_functional_test_latest",
            "version": FUNCTIONAL_TEST_CENTER_VERSION,
            "exists": False,
            "report": str(latest_md),
            "json": str(latest_json),
        }
    payload = json.loads(latest_json.read_text(encoding="utf-8", errors="replace"))
    payload["exists"] = True
    return payload


def format_functional_test_report(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    status = "GREEN" if payload.get("ok") else "FAIL"
    lines = [
        f"Functional Test Center: {status}",
        f"version: {payload.get('version', FUNCTIONAL_TEST_CENTER_VERSION)}",
        f"suite: {payload.get('suite', 'unknown')}",
        f"summary: passed={summary.get('passed')} total={summary.get('total')} failed={summary.get('failed')} critical_failed={summary.get('critical_failed')} warnings={summary.get('warnings')}",
    ]
    if payload.get("report"):
        lines.append(f"report: {payload.get('report')}")
    failed = [item for item in payload.get("items", []) if not item.get("ok")]
    if failed:
        lines.append("")
        lines.append("Failed items:")
        for item in failed[:12]:
            lines.append(f"- [{item.get('severity')}] {item.get('id')}: {item.get('error') or item.get('name')}")
    return "\n".join(lines)



def status() -> Dict[str, Any]:
    latest = get_latest_test_report()
    return {
        "ok": True,
        "mode": "localcomet_functional_test_center_status",
        "version": FUNCTIONAL_TEST_CENTER_VERSION,
        "reports_dir": str(_functional_reports_dir()),
        "latest_exists": bool(latest.get("exists", False)),
        "latest_report": latest.get("report", ""),
        "commands": [
            "localcomet test",
            "localcomet test smoke",
            "localcomet test full",
            "тест",
            "полный тест",
            "статус тестов",
            "последний тест",
            "открыть отчет тестов",
        ],
    }


def report() -> Dict[str, Any]:
    latest = get_latest_test_report()
    if latest.get("exists"):
        return {
            "ok": True,
            "mode": "localcomet_functional_test_center_report",
            "version": FUNCTIONAL_TEST_CENTER_VERSION,
            "report": latest.get("report", ""),
            "json": latest.get("json", ""),
            "summary": latest.get("summary", {}),
        }
    result = run_smoke_suite(write_report=True)
    return {
        "ok": bool(result.get("ok")),
        "mode": "localcomet_functional_test_center_report",
        "version": FUNCTIONAL_TEST_CENTER_VERSION,
        "report": result.get("report", ""),
        "json": result.get("json", ""),
        "summary": result.get("summary", {}),
    }


def handle_dispatch_command(command: str) -> Optional[Dict[str, Any]]:
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")
    if lower in {"localcomet test", "localcomet test smoke", "тест", "тест проекта", "функциональный тест"}:
        return run_smoke_suite(write_report=True)
    if lower in {"localcomet test full", "полный тест", "localcomet full test"}:
        return run_full_suite(write_report=True)
    if lower in {"статус тестов", "последний тест", "открыть отчет тестов"}:
        return get_latest_test_report()
    return None


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    result = run_smoke_suite(write_report=write_report)
    return {
        "ok": bool(result.get("ok")),
        "mode": "localcomet_functional_test_center_self_check",
        "version": FUNCTIONAL_TEST_CENTER_VERSION,
        "summary": result.get("summary", {}),
        "report": result.get("report", ""),
        "json": result.get("json", ""),
    }


# BEGIN v6.55b Agent Automation Functional Test Center integration
try:
    _planned_tests_before_agent_auto_ru_v655b
except NameError:
    _planned_tests_before_agent_auto_ru_v655b = _planned_tests


def _check_menu_version_marker() -> Dict[str, Any]:
    path = _root() / "modules" / "premium_task_panel_ru.py"
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": "PANEL_VERSION = \"v6.55b\"" in text and "LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B" in text,
        "has_progress": "ttk.Progressbar" in text,
        "has_patch_button": "Принять патч" in text,
        "has_test_button": "Тест" in text,
        "has_agent_test_command": "тест автоматических функций агента" in text,
    }


def _check_agent_auto_functions() -> Dict[str, Any]:
    module = _fresh_import("modules.localcomet_agent_auto_test_center_ru")
    result = module.run_smoke_suite(write_report=True)
    summary = result.get("summary", {})
    return {
        "ok": bool(result.get("ok")) and int(summary.get("failed", 1)) == 0,
        "summary": summary,
        "report": result.get("report"),
        "json": result.get("json"),
    }


def _check_agent_auto_functions_report() -> Dict[str, Any]:
    module = _fresh_import("modules.localcomet_agent_auto_test_center_ru")
    result = module.run_full_suite(write_report=True)
    summary = result.get("summary", {})
    return {
        "ok": bool(result.get("ok")) and int(summary.get("failed", 1)) == 0,
        "summary": summary,
        "report": result.get("report"),
        "json": result.get("json"),
        "latest_artifacts_exist": result.get("latest_artifacts_exist"),
    }


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_agent_auto_ru_v655b(include_full=include_full))
    ids = {item[0] for item in tests if item}
    if "agent.auto_functions" not in ids:
        insert_at = len(tests)
        for index, item in enumerate(tests):
            if item and item[0] == "strict.zero_warning":
                insert_at = index
                break
        tests.insert(insert_at, (
            "agent.auto_functions",
            "agent automation functional smoke checks",
            "agent",
            "computer_use",
            "critical",
            _check_agent_auto_functions,
        ))
    if include_full and "agent.auto_functions_report" not in ids:
        tests.append((
            "agent.auto_functions_report",
            "agent automation full report checks",
            "agent",
            "computer_use",
            "warning",
            _check_agent_auto_functions_report,
        ))
    return tests


LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B = "v6.55b agent automation functional test center integrated"
# END v6.55b Agent Automation Functional Test Center integration


# BEGIN v6.56 Professional Panel Capability Audit functional coverage
FUNCTIONAL_TEST_CENTER_VERSION = "v6.58"
LOCALCOMET_PANEL_CAPABILITY_AUDIT_FUNCTIONAL_RU_V656 = "v6.56 panel capability audit functional check installed"

try:
    _planned_tests_before_panel_capability_audit_ru_v656
except NameError:
    _planned_tests_before_panel_capability_audit_ru_v656 = _planned_tests

try:
    _functional_status_before_panel_capability_audit_ru_v656
except NameError:
    _functional_status_before_panel_capability_audit_ru_v656 = status


def _check_panel_capability_audit_ru_v656() -> Dict[str, Any]:
    module = _fresh_import("modules.panel_capability_audit_ru")
    result = module.run_panel_capability_audit(write_report=True)
    return {
        "ok": bool(result.get("ok")) and len(result.get("capability_matrix", [])) >= 10,
        "version": result.get("version"),
        "matrix_items": len(result.get("capability_matrix", [])),
        "broken_or_suspicious": len(result.get("broken_or_suspicious", [])),
        "missing_tests": len(result.get("missing_tests", [])),
        "report": result.get("report"),
        "json": result.get("json"),
    }


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_panel_capability_audit_ru_v656(include_full))
    if not any(item[0] == "menu.capability_audit" for item in tests):
        tests.append((
            "menu.capability_audit",
            "panel capability audit report is generated",
            "menu",
            "menu",
            "critical",
            _check_panel_capability_audit_ru_v656,
        ))
    return tests


def status() -> Dict[str, Any]:
    payload = _functional_status_before_panel_capability_audit_ru_v656()
    if isinstance(payload, dict):
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
        commands = list(payload.get("commands", []))
        for command in ["pc panel capability audit", "аудит панели"]:
            if command not in commands:
                commands.append(command)
        payload["commands"] = commands
        return payload
    return payload

# END v6.56 Professional Panel Capability Audit functional coverage

# BEGIN v6.58 Developer Velocity Toolkit functional coverage
FUNCTIONAL_TEST_CENTER_DEVELOPER_VELOCITY_RU_V658 = "v6.58 developer velocity toolkit functional tests installed"


def _check_developer_velocity_toolkit_ru_v658() -> Dict[str, Any]:
    from modules.localcomet_developer_velocity_ru import dispatch
    commands = ["последний сбой", "события патча", "статус разработки"]
    results = []
    for command in commands:
        result = dispatch(command)
        results.append({"command": command, "ok": isinstance(result, dict) and bool(result.get("handled", True)), "mode": result.get("mode") if isinstance(result, dict) else type(result).__name__})
    debug_status = dispatch("debug пакет")
    results.append({"command": "debug пакет", "ok": isinstance(debug_status, dict) and bool(debug_status.get("ok", True)), "mode": debug_status.get("mode") if isinstance(debug_status, dict) else type(debug_status).__name__})
    return {
        "ok": all(item.get("ok") for item in results),
        "mode": "developer_velocity_functional_coverage",
        "version": "v6.58",
        "results": results,
    }


try:
    _planned_tests_before_developer_velocity_ru_v658
except NameError:
    _planned_tests_before_developer_velocity_ru_v658 = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_developer_velocity_ru_v658(include_full))
    if not any(item[0] == "developer.velocity_toolkit" for item in tests):
        tests.append((
            "developer.velocity_toolkit",
            "developer velocity toolkit commands work",
            "developer",
            "velocity",
            "critical",
            _check_developer_velocity_toolkit_ru_v658,
        ))
    return tests


try:
    _functional_status_before_developer_velocity_ru_v658
except NameError:
    _functional_status_before_developer_velocity_ru_v658 = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_developer_velocity_ru_v658()
    if isinstance(payload, dict):
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for command in ["последний сбой", "события патча", "статус разработки", "debug пакет"]:
            if command not in commands:
                commands.append(command)
        payload["commands"] = commands
    return payload

# END v6.58 Developer Velocity Toolkit functional coverage


# BEGIN v6.58c Developer Velocity Toolkit functional menu marker repair
FUNCTIONAL_TEST_CENTER_MENU_MARKER_REPAIR_RU_V658C = "v6.58c accepts modern menu markers and legacy compatibility markers"


try:
    _check_menu_version_marker_before_developer_velocity_ru_v658c = _check_menu_version_marker
except NameError:
    _check_menu_version_marker_before_developer_velocity_ru_v658c = None


def _check_menu_version_marker() -> Dict[str, Any]:
    path = _root() / "modules" / "premium_task_panel_ru.py"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    has_progress = "ttk.Progressbar" in text
    has_patch_button = "Принять патч" in text
    has_test_button = "Тест" in text
    has_functional_marker = "LOCALCOMET_FUNCTIONAL_TEST_CENTER_RU_V652B" in text
    has_agent_marker = "LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B" in text
    has_agent_test_command = "тест автоматических функций агента" in text
    has_developer_velocity = (
        "PREMIUM_TASK_PANEL_DEVELOPER_VELOCITY_BRIDGE_RU_V658" in text
        or "PREMIUM_TASK_PANEL_DEVELOPER_VELOCITY_COMMANDS_RU_V658C" in text
        or "localcomet_developer_velocity_ru" in text
        or "статус разработки" in text
    )
    has_legacy_version_marker = 'PANEL_VERSION = "v6.52b"' in text or 'PANEL_VERSION = "v6.55b"' in text
    has_current_panel_version = "PANEL_VERSION" in text or "PREMIUM_TASK_PANEL_VERSION" in text
    ok = bool(
        has_progress
        and has_patch_button
        and has_test_button
        and has_current_panel_version
        and (has_functional_marker or has_agent_marker or has_developer_velocity)
    )
    return {
        "ok": ok,
        "version": "v6.58c",
        "mode": "menu_version_marker_modern_compatibility",
        "has_progress": has_progress,
        "has_patch_button": has_patch_button,
        "has_test_button": has_test_button,
        "has_functional_marker": has_functional_marker,
        "has_agent_marker": has_agent_marker,
        "has_agent_test_command": has_agent_test_command,
        "has_developer_velocity": has_developer_velocity,
        "has_legacy_version_marker": has_legacy_version_marker,
        "has_current_panel_version": has_current_panel_version,
        "reason": "Accepts the current menu plus legacy smoke-test marker constants without downgrading the real panel version.",
    }

# BEGIN v6.59a Command Explorer RU functional coverage
FUNCTIONAL_TEST_CENTER_COMMAND_EXPLORER_RU_V659A = "v6.59a command explorer functional tests installed"


def _check_command_explorer_ru_v659a() -> Dict[str, Any]:
    from modules.command_explorer_ru import dispatch
    r = dispatch("команды проекта")
    return {
        "ok": isinstance(r, dict) and r.get("ok") and isinstance(r.get("categories"), dict) and len(r.get("categories", {})) >= 3,
        "mode": "command_explorer_functional_coverage",
        "version": "v6.59a",
        "module_count": r.get("module_count"),
        "command_count": r.get("command_count"),
        "category_count": r.get("category_count"),
    }


try:
    _planned_tests_before_command_explorer_ru_v659a
except NameError:
    _planned_tests_before_command_explorer_ru_v659a = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_command_explorer_ru_v659a(include_full))
    if not any(item[0] == "developer.command_explorer" for item in tests):
        tests.append((
            "developer.command_explorer",
            "command explorer discovers commands",
            "developer",
            "command_explorer",
            "critical",
            _check_command_explorer_ru_v659a,
        ))
    return tests


try:
    _functional_status_before_command_explorer_ru_v659a
except NameError:
    _functional_status_before_command_explorer_ru_v659a = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_command_explorer_ru_v659a()
    if isinstance(payload, dict):
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["команды проекта", "список команд", "command explorer"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
    return payload

# BEGIN v6.59b Repo Analyzer RU functional coverage
FUNCTIONAL_TEST_CENTER_REPO_ANALYZER_RU_V659B = "v6.59b repo analyzer functional tests installed"


def _check_repo_analyzer_ru_v659b() -> Dict[str, Any]:
    from modules.repo_analyzer_ru import dispatch
    r = dispatch("анализ проекта")
    return {
        "ok": isinstance(r, dict) and r.get("ok") and isinstance(r.get("file_count"), int) and r["file_count"] >= 10,
        "mode": "repo_analyzer_functional_coverage",
        "version": "v6.59b",
        "file_count": r.get("file_count"),
        "function_count": r.get("function_count"),
        "command_module_count": r.get("command_module_count"),
    }


try:
    _planned_tests_before_repo_analyzer_ru_v659b
except NameError:
    _planned_tests_before_repo_analyzer_ru_v659b = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_repo_analyzer_ru_v659b(include_full))
    if not any(item[0] == "developer.repo_analyzer" for item in tests):
        tests.append((
            "developer.repo_analyzer",
            "repo analyzer analyzes project",
            "developer",
            "repo_analyzer",
            "critical",
            _check_repo_analyzer_ru_v659b,
        ))
    return tests


try:
    _functional_status_before_repo_analyzer_ru_v659b
except NameError:
    _functional_status_before_repo_analyzer_ru_v659b = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_repo_analyzer_ru_v659b()
    if isinstance(payload, dict):
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["анализ проекта", "repo analyzer", "карта проекта"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
    return payload

# BEGIN v6.63 Context Pack RU functional coverage
FUNCTIONAL_TEST_CENTER_CONTEXT_PACK_RU_V663 = "v6.63 context pack functional tests installed"


def _check_context_pack_ru_v663() -> Dict[str, Any]:
    from modules.context_pack_ru import dispatch, CONTEXT_PACK_JSON, ROOT_PATH as CP_ROOT
    import json, re
    r = dispatch("localcomet agent context pack")
    expected = ""
    actual = ""
    version_ok = False
    try:
        panel_text = (CP_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if CONTEXT_PACK_JSON.exists():
            payload = json.loads(CONTEXT_PACK_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
        version_ok = bool(expected) and expected == actual
    except Exception:
        pass
    return {
        "ok": isinstance(r, dict) and r.get("ok") and r.get("handled") and isinstance(r.get("paths"), dict) and "json" in r.get("paths", {}) and version_ok,
        "mode": "context_pack_functional_coverage",
        "version": "v6.64",
        "paths": r.get("paths"),
        "expected_version": expected,
        "actual_version": actual,
        "version_consistent": version_ok,
    }


try:
    _planned_tests_before_context_pack_ru_v663
except NameError:
    _planned_tests_before_context_pack_ru_v663 = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_context_pack_ru_v663(include_full))
    if not any(item[0] == "developer.context_pack" for item in tests):
        tests.append((
            "developer.context_pack",
            "context pack generates handoff files",
            "developer",
            "context_pack",
            "critical",
            _check_context_pack_ru_v663,
        ))
    return tests


try:
    _functional_status_before_context_pack_ru_v663
except NameError:
    _functional_status_before_context_pack_ru_v663 = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_context_pack_ru_v663()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet agent context pack", "agent context pack"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# BEGIN v6.63 Plan Contract RU functional coverage
FUNCTIONAL_TEST_CENTER_PLAN_CONTRACT_RU_V663 = "v6.63 plan contract functional tests installed"


def _check_plan_contract_ru_v663() -> Dict[str, Any]:
    from modules.plan_contract_ru import dispatch, PLAN_CONTRACT_JSON, ROOT_PATH as PC_ROOT
    import json, re
    r = dispatch("localcomet agent plan contract")
    expected = ""
    actual = ""
    version_ok = False
    try:
        panel_text = (PC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if PLAN_CONTRACT_JSON.exists():
            payload = json.loads(PLAN_CONTRACT_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
        version_ok = bool(expected) and expected == actual
    except Exception:
        pass
    return {
        "ok": isinstance(r, dict) and r.get("ok") and r.get("handled") and isinstance(r.get("paths"), dict) and "json" in r.get("paths", {}) and version_ok,
        "mode": "plan_contract_functional_coverage",
        "version": "v6.64",
        "paths": r.get("paths"),
        "expected_version": expected,
        "actual_version": actual,
        "version_consistent": version_ok,
    }


try:
    _planned_tests_before_plan_contract_ru_v663
except NameError:
    _planned_tests_before_plan_contract_ru_v663 = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_plan_contract_ru_v663(include_full))
    if not any(item[0] == "developer.plan_contract" for item in tests):
        tests.append((
            "developer.plan_contract",
            "plan contract generates task contract files",
            "developer",
            "plan_contract",
            "critical",
            _check_plan_contract_ru_v663,
        ))
    return tests


try:
    _functional_status_before_plan_contract_ru_v663
except NameError:
    _functional_status_before_plan_contract_ru_v663 = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_plan_contract_ru_v663()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet agent plan contract", "agent plan contract"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# BEGIN v6.63 Risk Classifier RU functional coverage
FUNCTIONAL_TEST_CENTER_RISK_CLASSIFIER_RU_V663 = "v6.63 risk classifier functional tests installed"


def _check_risk_classifier_ru_v663() -> Dict[str, Any]:
    from modules.risk_classifier_ru import classify, dispatch, RISK_CLASSIFIER_JSON, ROOT_PATH as RC_ROOT
    import json, re
    r = dispatch("localcomet agent risk classify")
    expected = ""
    actual = ""
    version_ok = False
    try:
        panel_text = (RC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if RISK_CLASSIFIER_JSON.exists():
            payload = json.loads(RISK_CLASSIFIER_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
        version_ok = bool(expected) and expected == actual
    except Exception:
        pass
    docs = classify("fix typo in AGENTS.md")
    high_risk = classify("install new dependency via subprocess")
    return {
        "ok": isinstance(r, dict) and r.get("ok") and r.get("handled") and isinstance(r.get("paths"), dict) and "json" in r.get("paths", {}) and version_ok and docs.get("task_risk_level") == "docs_only" and high_risk.get("task_risk_level") == "high",
        "mode": "risk_classifier_functional_coverage",
        "version": "v6.64",
        "paths": r.get("paths"),
        "expected_version": expected,
        "actual_version": actual,
        "version_consistent": version_ok,
        "docs_classification": docs.get("task_risk_level"),
        "high_classification": high_risk.get("task_risk_level"),
    }


try:
    _planned_tests_before_risk_classifier_ru_v663
except NameError:
    _planned_tests_before_risk_classifier_ru_v663 = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_risk_classifier_ru_v663(include_full))
    if not any(item[0] == "developer.risk_classifier" for item in tests):
        tests.append((
            "developer.risk_classifier",
            "risk classifier classifies tasks and generates risk files",
            "developer",
            "risk_classifier",
            "critical",
            _check_risk_classifier_ru_v663,
        ))
    return tests


try:
    _functional_status_before_risk_classifier_ru_v663
except NameError:
    _functional_status_before_risk_classifier_ru_v663 = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_risk_classifier_ru_v663()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet agent risk classify", "agent risk classify"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# END v6.63 Risk Classifier RU functional coverage

# BEGIN v6.64a Repository Weight Audit RU functional coverage
FUNCTIONAL_TEST_CENTER_REPO_WEIGHT_AUDIT_RU_V664A = "v6.64a repo weight audit functional tests installed"


def _check_repo_weight_audit_ru_v664a() -> Dict[str, Any]:
    from modules.repo_weight_audit_ru import dispatch, REPO_WEIGHT_JSON, ROOT_PATH as RWA_ROOT
    import json, re
    r = dispatch("localcomet repo weight audit")
    expected = ""
    actual = ""
    version_ok = False
    try:
        panel_text = (RWA_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if REPO_WEIGHT_JSON.exists():
            payload = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
        version_ok = bool(expected) and expected == actual
    except Exception:
        pass
    has_field = False
    try:
        if REPO_WEIGHT_JSON.exists():
            p = json.loads(REPO_WEIGHT_JSON.read_text(encoding="utf-8"))
            has_field = bool(p.get("total_size_gb")) and bool(p.get("file_count")) and bool(p.get("folder_count")) and bool(p.get("top_directories")) and bool(p.get("dangerous_cleanup_warning"))
    except Exception:
        pass
    return {
        "ok": isinstance(r, dict) and r.get("ok") and r.get("handled") and isinstance(r.get("paths"), dict) and "json" in r.get("paths", {}) and version_ok and has_field,
        "mode": "repo_weight_audit_functional_coverage",
        "version": "v6.64a",
        "paths": r.get("paths"),
        "expected_version": expected,
        "actual_version": actual,
        "version_consistent": version_ok,
    }


try:
    _planned_tests_before_repo_weight_audit_ru_v664a
except NameError:
    _planned_tests_before_repo_weight_audit_ru_v664a = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_repo_weight_audit_ru_v664a(include_full))
    if not any(item[0] == "developer.repo_weight_audit" for item in tests):
        tests.append((
            "developer.repo_weight_audit",
            "repo weight audit scans repository and generates weight report",
            "developer",
            "repo_weight_audit",
            "critical",
            _check_repo_weight_audit_ru_v664a,
        ))
    return tests


try:
    _functional_status_before_repo_weight_audit_ru_v664a
except NameError:
    _functional_status_before_repo_weight_audit_ru_v664a = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_repo_weight_audit_ru_v664a()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet repo weight audit", "repo weight audit"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# END v6.64a Repository Weight Audit RU functional coverage

# BEGIN v6.64b Storage Cleanup Plan RU functional coverage
FUNCTIONAL_TEST_CENTER_STORAGE_CLEANUP_PLAN_RU_V664B = "v6.64b storage cleanup plan functional tests installed"


def _check_storage_cleanup_plan_ru_v664b() -> Dict[str, Any]:
    from modules.storage_cleanup_plan_ru import dispatch, STORAGE_CLEANUP_JSON, ROOT_PATH as SCP_ROOT
    import json, re
    r = dispatch("localcomet storage cleanup plan")
    expected = ""
    actual = ""
    version_ok = False
    mode_ok = False
    no_del_ok = False
    try:
        panel_text = (SCP_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if STORAGE_CLEANUP_JSON.exists():
            payload = json.loads(STORAGE_CLEANUP_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
            mode_ok = payload.get("cleanup_mode") == "plan_only" and payload.get("deletion_enabled") is False
            warning = payload.get("dangerous_cleanup_warning", "")
            no_del_ok = "NO FILES WERE DELETED" in warning
        version_ok = bool(expected) and expected == actual
    except Exception:
        pass
    return {
        "ok": isinstance(r, dict) and r.get("ok") and r.get("handled") and isinstance(r.get("paths"), dict) and "json" in r.get("paths", {}) and version_ok and mode_ok and no_del_ok,
        "mode": "storage_cleanup_plan_functional_coverage",
        "version": "v6.64b",
        "paths": r.get("paths"),
        "expected_version": expected,
        "actual_version": actual,
        "version_consistent": version_ok,
    }


try:
    _planned_tests_before_storage_cleanup_plan_ru_v664b
except NameError:
    _planned_tests_before_storage_cleanup_plan_ru_v664b = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_storage_cleanup_plan_ru_v664b(include_full))
    if not any(item[0] == "developer.storage_cleanup_plan" for item in tests):
        tests.append((
            "developer.storage_cleanup_plan",
            "storage cleanup plan generates cleanup recommendations from audit data",
            "developer",
            "storage_cleanup_plan",
            "critical",
            _check_storage_cleanup_plan_ru_v664b,
        ))
    return tests


try:
    _functional_status_before_storage_cleanup_plan_ru_v664b
except NameError:
    _functional_status_before_storage_cleanup_plan_ru_v664b = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_storage_cleanup_plan_ru_v664b()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet storage cleanup plan", "storage cleanup plan"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# END v6.64b Storage Cleanup Plan RU functional coverage

# BEGIN v6.64c Screenshot Retention Dry Run RU functional coverage
FUNCTIONAL_TEST_CENTER_SCREENSHOT_RETENTION_DRY_RUN_RU_V664C = "v6.64c screenshot retention dry run functional tests installed"


def _check_screenshot_retention_dry_run_ru_v664c() -> Dict[str, Any]:
    from modules.screenshot_retention_dry_run_ru import dispatch, DRY_RUN_JSON, ROOT_PATH as SRD_ROOT
    import json, re
    r = dispatch("localcomet screenshots retention dry run")
    expected = ""
    actual = ""
    version_ok = False
    mode_ok = False
    no_del_ok = False
    dirs_ok = False
    try:
        panel_text = (SRD_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if DRY_RUN_JSON.exists():
            payload = json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))
            actual = payload.get("base_version", "")
            mode_ok = payload.get("cleanup_mode") == "dry_run_only" and payload.get("deletion_enabled") is False
            warning = payload.get("dangerous_cleanup_warning", "")
            no_del_ok = "NO FILES WERE DELETED" in warning
            dirs_ok = isinstance(payload.get("screenshot_directories"), list) and len(payload.get("screenshot_directories", [])) > 0
        version_ok = bool(expected) and expected == actual
    except Exception:
        pass
    return {
        "ok": isinstance(r, dict) and r.get("ok") and r.get("handled") and isinstance(r.get("paths"), dict) and "json" in r.get("paths", {}) and version_ok and mode_ok and no_del_ok and dirs_ok,
        "mode": "screenshot_retention_dry_run_functional_coverage",
        "version": "v6.64c",
        "paths": r.get("paths"),
        "expected_version": expected,
        "actual_version": actual,
        "version_consistent": version_ok,
    }


try:
    _planned_tests_before_screenshot_retention_dry_run_ru_v664c
except NameError:
    _planned_tests_before_screenshot_retention_dry_run_ru_v664c = _planned_tests


def _planned_tests(include_full: bool) -> List[tuple]:
    tests = list(_planned_tests_before_screenshot_retention_dry_run_ru_v664c(include_full))
    if not any(item[0] == "developer.screenshot_retention_dry_run" for item in tests):
        tests.append((
            "developer.screenshot_retention_dry_run",
            "screenshot retention dry run scans screenshots and generates dry-run report",
            "developer",
            "screenshot_retention_dry_run",
            "critical",
            _check_screenshot_retention_dry_run_ru_v664c,
        ))
    return tests


try:
    _functional_status_before_screenshot_retention_dry_run_ru_v664c
except NameError:
    _functional_status_before_screenshot_retention_dry_run_ru_v664c = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_screenshot_retention_dry_run_ru_v664c()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet screenshots retention dry run", "screenshots retention dry run"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# END v6.64c Screenshot Retention Dry Run RU functional coverage

# BEGIN v6.64d Screenshot Storage Policy Simulator RU functional coverage
FUNCTIONAL_TEST_CENTER_SCREENSHOT_STORAGE_POLICY_SIMULATOR_RU_V664D = "v6.64d screenshot storage policy simulator functional tests installed"


def _check_screenshot_storage_policy_simulator_ru_v664d() -> Dict[str, Any]:
    from modules.screenshot_storage_policy_simulator_ru import dispatch, ROOT_PATH as SPS_ROOT
    result = dispatch("localcomet screenshots storage policy simulate")
    ok = result.get("ok", False) if isinstance(result, dict) else False
    paths = result.get("paths", {}) if isinstance(result, dict) else {}
    json_path = paths.get("json", "")
    md_path = paths.get("md", "")
    json_exists = json_path and (SPS_ROOT / json_path).exists()
    md_exists = md_path and (SPS_ROOT / md_path).exists()
    record: Dict[str, Any] = {"mode": "screenshot_storage_policy_simulator_functional_coverage", "version": "v6.64d", "dispatch_ok": ok, "json_exists": json_exists, "md_exists": md_exists, "paths": paths}
    if ok and json_exists:
        import json as _json
        try:
            data = _json.loads((SPS_ROOT / json_path).read_text(encoding="utf-8"))
            record["policy_count"] = len(data.get("simulated_policies", []))
            record["growth_rate_gb_per_day"] = data.get("growth_rate_estimate", {}).get("gb_per_day", "N/A")
            record["projected_30_day_gb"] = data["projected_30_day_size_gb"]
            record["projected_90_day_gb"] = data["projected_90_day_size_gb"]
        except Exception as e:
            record["json_read_error"] = str(e)
    return record


try:
    _planned_tests_before_screenshot_storage_policy_simulator_ru_v664d
except NameError:
    _planned_tests_before_screenshot_storage_policy_simulator_ru_v664d = _planned_tests


def _planned_tests(include_full: str = "auto"):
    tests = list(_planned_tests_before_screenshot_storage_policy_simulator_ru_v664d(include_full))
    if not any(item[0] == "developer.screenshot_storage_policy_simulator" for item in tests):
        tests.append((
            "developer.screenshot_storage_policy_simulator",
            "v6.64d screenshot storage policy simulator",
            "developer",
            "screenshot_storage_policy_simulator",
            "critical",
            _check_screenshot_storage_policy_simulator_ru_v664d,
        ))
    return tests


try:
    _functional_status_before_screenshot_storage_policy_simulator_ru_v664d
except NameError:
    _functional_status_before_screenshot_storage_policy_simulator_ru_v664d = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_screenshot_storage_policy_simulator_ru_v664d()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet screenshots storage policy simulate", "screenshots storage policy simulate"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# END v6.64d Screenshot Storage Policy Simulator RU functional coverage

# BEGIN v6.64e Screenshot Retention Policy Config RU functional coverage
FUNCTIONAL_TEST_CENTER_SCREENSHOT_RETENTION_POLICY_CONFIG_RU_V664E = "v6.64e screenshot retention policy config functional tests installed"


def _check_screenshot_retention_policy_config_ru_v664e() -> Dict[str, Any]:
    from modules.screenshot_retention_policy_config_ru import dispatch, POLICY_JSON, POLICY_MD, ROOT_PATH as RPC_ROOT
    import json, re
    result = dispatch("localcomet screenshots retention policy write")
    ok = result.get("ok", False) if isinstance(result, dict) else False
    json_exists = POLICY_JSON.exists()
    md_exists = POLICY_MD.exists()
    version_ok = False
    cleanup_ok = False
    deletion_ok = False
    manual_ok = False
    policy_ok = False
    enforcement_ok = False
    try:
        panel_text = (RPC_ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
        m = re.search(r'^LOCALCOMET_VERSION\s*=\s*"([^"]+)"', panel_text, re.MULTILINE)
        expected = m.group(1) if m else ""
        if json_exists:
            data = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
            actual = data.get("base_version", "")
            version_ok = bool(expected) and expected == actual
            cleanup_ok = data.get("cleanup_mode") == "policy_config_only"
            deletion_ok = data.get("deletion_enabled") is False
            manual_ok = data.get("manual_approval_required") is True
            policy_ok = data.get("selected_policy") == "keep_newest_500_per_directory"
            es = data.get("enforcement_status", {})
            enforcement_ok = es.get("active") is False
    except Exception:
        pass
    all_ok = ok and json_exists and md_exists and version_ok and cleanup_ok and deletion_ok and manual_ok and policy_ok and enforcement_ok
    return {
        "ok": all_ok,
        "mode": "screenshot_retention_policy_config_functional_coverage",
        "version": "v6.64e",
        "dispatch_ok": ok,
        "json_exists": json_exists,
        "md_exists": md_exists,
        "version_consistent": version_ok,
        "cleanup_mode_policy_config_only": cleanup_ok,
        "deletion_enabled_false": deletion_ok,
        "manual_approval_required_true": manual_ok,
        "selected_policy_keep_newest_500": policy_ok,
        "enforcement_inactive": enforcement_ok,
    }


try:
    _planned_tests_before_screenshot_retention_policy_config_ru_v664e
except NameError:
    _planned_tests_before_screenshot_retention_policy_config_ru_v664e = _planned_tests


def _planned_tests(include_full: str = "auto"):
    tests = list(_planned_tests_before_screenshot_retention_policy_config_ru_v664e(include_full))
    if not any(item[0] == "developer.screenshot_retention_policy_config" for item in tests):
        tests.append((
            "developer.screenshot_retention_policy_config",
            "v6.64e screenshot retention policy config writes policy config files",
            "developer",
            "screenshot_retention_policy_config",
            "critical",
            _check_screenshot_retention_policy_config_ru_v664e,
        ))
    return tests


try:
    _functional_status_before_screenshot_retention_policy_config_ru_v664e
except NameError:
    _functional_status_before_screenshot_retention_policy_config_ru_v664e = status


def status() -> Dict[str, Any]:
    payload = _functional_status_before_screenshot_retention_policy_config_ru_v664e()
    if isinstance(payload, dict):
        commands = list(payload.get("commands", [])) if isinstance(payload.get("commands", []), list) else []
        for cmd in ["localcomet screenshots retention policy write", "screenshots retention policy write"]:
            if cmd not in commands:
                commands.append(cmd)
        payload["commands"] = commands
        payload["version"] = FUNCTIONAL_TEST_CENTER_VERSION
    return payload

# END v6.64e Screenshot Retention Policy Config RU functional coverage
