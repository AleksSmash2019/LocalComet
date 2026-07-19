from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional, Tuple


PATCH_PANEL_VERSION = "v6.58"
PATCH_PANEL_NAME = "Patch Panel UX Reliability + Developer Velocity Service RU"
PATCH_PANEL_RETIRED_SERVICE_VERSION = "v6.52b"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent

PROJECTS_DIR = ROOT_DIR / "Projects"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
REPORTS_DIR = PROJECTS_DIR / "Reports"
LOGS_DIR = PROJECTS_DIR / "Logs"
RESPONSE_FILE = RELAY_DIR / "response.json"
BAD_RESPONSE_FILE = RELAY_DIR / "bad_response.json"
SELECTED_RESPONSE_SOURCE_FILE = RELAY_DIR / "selected_response_source.txt"
USER_DOWNLOADS_DIR = Path.home() / "Downloads"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value: Any, limit: int = 3500) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[trimmed]"


def _ensure_project_import_path() -> None:
    root_text = str(ROOT_DIR)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _fresh_import(module_name: str):
    _ensure_project_import_path()
    importlib.invalidate_caches()
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _read_text(path: Path, default: str = "") -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return default
    return default


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")


def _copy_file_bytes(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def validate_response_payload(payload: Any) -> Tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "response.json должен быть JSON object."
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return False, "response.json должен содержать непустую строку summary."
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        return False, "response.json должен содержать непустой список operations."
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            return False, f"operation #{index} не является object."
        if "type" not in operation:
            return False, f"operation #{index} должен использовать ключ type."
        if "op" in operation:
            return False, f"operation #{index} использует запрещенный ключ op."
        if operation.get("type") not in {"create", "replace", "append", "delete"}:
            return False, f"operation #{index} имеет неизвестный type: {operation.get('type')}"
        if not isinstance(operation.get("path"), str) or not operation.get("path", "").strip():
            return False, f"operation #{index} должен содержать path."
    tests = payload.get("tests")
    if not isinstance(tests, list) or not tests:
        return False, "response.json должен содержать непустой список tests."
    return True, "OK"


def _load_response_payload(path: Path) -> Tuple[bool, str, Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return False, f"Файл response не найден: {path}", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception as exc:
        return False, f"Не удалось прочитать JSON: {exc}", {}
    ok, reason = validate_response_payload(payload)
    if not ok:
        return False, reason, payload if isinstance(payload, dict) else {}
    return True, "OK", payload


def _response_candidates_from_downloads() -> List[Path]:
    if not USER_DOWNLOADS_DIR.exists():
        return []
    candidates = [
        path for path in USER_DOWNLOADS_DIR.glob("response*.json")
        if path.is_file() and path.resolve() != RESPONSE_FILE.resolve()
    ]
    unique: Dict[str, Path] = {}
    for path in candidates:
        try:
            unique[str(path.resolve())] = path
        except Exception:
            continue
    return sorted(unique.values(), key=lambda item: item.stat().st_mtime, reverse=True)


def _selected_response_source() -> Optional[Path]:
    text = _read_text(SELECTED_RESPONSE_SOURCE_FILE).strip()
    if not text:
        return None
    try:
        path = Path(text)
    except Exception:
        return None
    try:
        if path.exists() and path.is_file() and path.resolve() != RESPONSE_FILE.resolve():
            return path
    except Exception:
        return None
    return None


def find_latest_response_file() -> Optional[Path]:
    selected = _selected_response_source()
    if selected is not None:
        return selected
    candidates = _response_candidates_from_downloads()
    return candidates[0] if candidates else None


def reset_selected_response_source_text() -> str:
    _write_text(SELECTED_RESPONSE_SOURCE_FILE, "")
    return "OK: выбранный response сброшен."


def import_specific_response_text(source: Path) -> str:
    source = Path(source)
    ok, reason, payload = _load_response_payload(source)
    if not ok:
        _write_text(BAD_RESPONSE_FILE, f"{source}\n\n{reason}\n\n{_short(payload)}")
        return (
            "STOP: выбранный response*.json не прошел локальную проверку.\n"
            f"Файл: {source}\n"
            f"Причина: {reason}\n"
            f"bad_response: {BAD_RESPONSE_FILE}"
        )
    _copy_file_bytes(source, RESPONSE_FILE)
    _write_text(SELECTED_RESPONSE_SOURCE_FILE, str(source))
    return (
        "OK: response.json импортирован.\n"
        f"Источник: {source}\n"
        f"Цель: {RESPONSE_FILE}\n"
        f"Summary: {payload.get('summary')}\n"
        f"Операций: {len(payload.get('operations', []))}\n"
        f"Тестов: {len(payload.get('tests', []))}"
    )


def import_latest_response_text() -> str:
    latest = find_latest_response_file()
    if latest is None:
        return (
            "STOP: не найден новый response*.json.\n"
            "Активный Projects/ChatGPTRelay/response.json не используется как источник, "
            "чтобы не переустановить старый patch.\n"
            f"Downloads: {USER_DOWNLOADS_DIR}\n"
            "Используй команду 'выбрать response C:\\path\\response.json'."
        )
    return import_specific_response_text(latest)


def validate_output_is_success(text: str) -> bool:
    lower = str(text or "").lower()
    success_markers = ["relay response: ✅ проверка пройдена", "✅ проверка пройдена", "проверка пройдена"]
    hard_fail_markers = [
        "relay response: ❌",
        "json parse error",
        "нет списка operations",
        "operations missing",
        "операций: 0",
        "stop:",
        "traceback",
        "assertionerror",
    ]
    return any(marker in lower for marker in success_markers) and not any(marker in lower for marker in hard_fail_markers)


def _code_lines_are_zero(text: str) -> bool:
    found_code = False
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip().lower()
        if not line.startswith("code:"):
            continue
        found_code = True
        value = line.split(":", 1)[1].strip()
        if value not in {"0", "0.0"}:
            return False
    return True if found_code else True


def apply_output_is_success(text: str) -> bool:
    raw = str(text or "")
    lower = raw.lower()
    success_markers = ["patch успешно применен", "patch registry:"]
    hard_fail_markers = [
        "ошибка применения patch",
        "изменения откачены",
        "patch применен, но тесты упали",
        "patch не применен",
        "relay response не импортирован",
        "traceback",
        "assertionerror",
    ]
    if any(marker in lower for marker in hard_fail_markers):
        return False
    if not _code_lines_are_zero(raw):
        return False
    return any(marker in lower for marker in success_markers)


def _format_json_compact(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=True, indent=2)
    except Exception:
        return str(payload)


def validate_relay_response_text() -> str:
    agent = _fresh_import("agents.chatgpt_relay_agent")
    return str(agent.handle("validate_response", {}))


def apply_relay_response_text() -> str:
    agent = _fresh_import("agents.chatgpt_relay_agent")
    return str(agent.handle("apply_response", {}))


def after_patch_text() -> str:
    agent = _fresh_import("agents.automation_agent")
    return str(agent.handle("after_patch", {}))


def run_project_checks_text() -> str:
    lines: List[str] = []
    try:
        center = _fresh_import("modules.localcomet_functional_test_center_ru")
        result = center.run_full_suite(write_report=True)
        lines.append("--- FUNCTIONAL TEST CENTER ---")
        lines.append(_format_json_compact({
            "ok": result.get("ok"),
            "mode": result.get("mode"),
            "version": result.get("version"),
            "summary": result.get("summary"),
            "report": result.get("report"),
        }))
        if not result.get("ok"):
            lines.append("STOP: functional test center не green.")
            return "\n".join(lines)
    except Exception:
        lines.append("--- FUNCTIONAL TEST CENTER ---")
        lines.append(traceback.format_exc())
        lines.append("STOP: functional test center завершился исключением.")
        return "\n".join(lines)

    try:
        core = _fresh_import("modules.computer_use_core_ru")
        contracts = core.dispatch("pc computer contracts")
        lines.append("\n--- COMPUTER USE CONTRACTS ---")
        lines.append(_format_json_compact({
            "ok": contracts.get("ok"),
            "mode": contracts.get("mode"),
            "summary": contracts.get("summary"),
            "report": contracts.get("report"),
        }))
        if not contracts.get("ok") or contracts.get("summary", {}).get("failed", 0) != 0:
            lines.append("STOP: pc computer contracts не прошли.")
            return "\n".join(lines)
    except Exception:
        lines.append("\n--- COMPUTER USE CONTRACTS ---")
        lines.append(traceback.format_exc())
        lines.append("STOP: computer use contracts завершились исключением.")
        return "\n".join(lines)

    try:
        strict = _fresh_import("modules.strict_project_stability_ru")
        strict_result = strict.dispatch("проверь проект")
        lines.append("\n--- STRICT PROJECT STABILITY ---")
        lines.append(_format_json_compact({
            "ok": strict_result.get("ok"),
            "score": strict_result.get("score"),
            "summary": strict_result.get("summary"),
            "report": strict_result.get("report"),
        }))
        summary = strict_result.get("summary", {})
        if not strict_result.get("ok") or summary.get("hard_failures", 1) != 0 or summary.get("warnings", 1) != 0:
            lines.append("STOP: strict_project_stability не прошел zero-warning gate.")
            return "\n".join(lines)
    except Exception:
        lines.append("\n--- STRICT PROJECT STABILITY ---")
        lines.append(traceback.format_exc())
        lines.append("STOP: strict_project_stability завершился исключением.")
        return "\n".join(lines)

    lines.append("\nOK: проект проверен. functional/contracts/strict green.")
    return "\n".join(lines)


def import_validate_apply_check_text() -> str:
    lines: List[str] = [f"LocalComet retired Patch Panel service {PATCH_PANEL_VERSION}", f"started_at: {_now()}"]
    import_result = import_latest_response_text()
    lines.append("\n--- IMPORT ---")
    lines.append(import_result)
    if not import_result.lstrip().startswith("OK:"):
        lines.append("\nSTOP: импорт response не прошел.")
        return "\n".join(lines)

    validate_result = validate_relay_response_text()
    lines.append("\n--- VALIDATE ---")
    lines.append(validate_result)
    if not validate_output_is_success(validate_result):
        lines.append("\nSTOP: relay validate не прошел. patch не применялся.")
        return "\n".join(lines)

    apply_result = apply_relay_response_text()
    lines.append("\n--- APPLY ---")
    lines.append(apply_result)
    if not apply_output_is_success(apply_result):
        lines.append("\nSTOP: apply не прошел. after patch и проверки не запущены.")
        return "\n".join(lines)

    try:
        after_result = after_patch_text()
    except Exception:
        after_result = traceback.format_exc()
    lines.append("\n--- AFTER PATCH ---")
    lines.append(after_result)

    checks_result = run_project_checks_text()
    lines.append("\n--- VERIFY ---")
    lines.append(checks_result)
    if "STOP:" in checks_result:
        lines.append("\nSTOP: patch применен, но проверки проекта не green.")
    else:
        lines.append("\nOK: patch принят и проверен через новое меню/backend service.")
    return "\n".join(lines)


def refresh_status_snapshot() -> str:
    lines: List[str] = [
        f"Patch backend service: {PATCH_PANEL_VERSION} - retired GUI",
        f"Project: {ROOT_DIR}",
        f"Relay response: {RESPONSE_FILE}",
        f"Downloads: {USER_DOWNLOADS_DIR}",
        f"updated_at: {_now()}",
    ]
    selected = _selected_response_source()
    latest = _response_candidates_from_downloads()[0] if _response_candidates_from_downloads() else None
    lines.append(f"selected response source: {selected if selected else 'нет'}")
    lines.append(f"latest Downloads response: {latest if latest else 'нет'}")
    if RESPONSE_FILE.exists():
        ok, reason, payload = _load_response_payload(RESPONSE_FILE)
        lines.append(f"active relay response.json: {'ok' if ok else 'bad'}")
        if ok:
            lines.append(f"active response summary: {_short(payload.get('summary'), 500)}")
            lines.append(f"operations: {len(payload.get('operations', []))}")
            lines.append(f"tests: {len(payload.get('tests', []))}")
        else:
            lines.append(f"active response reason: {reason}")
    else:
        lines.append("active relay response.json: отсутствует")
    try:
        project_paths = _fresh_import("modules.project_paths")
        status = project_paths.status()
        lines.append(f"project_paths: {status.get('version')} ok={status.get('ok')}")
    except Exception:
        lines.append("project_paths: ошибка")
        lines.append(_short(traceback.format_exc(), 1000))
    try:
        patch_registry = _fresh_import("modules.patch_registry")
        latest_patch = patch_registry.get_latest_patch()
        lines.append(f"latest registry version: {latest_patch.get('version') or 'нет'}")
        lines.append(f"latest registry status: {latest_patch.get('status') or 'нет'}")
    except Exception:
        lines.append("patch registry: ошибка")
        lines.append(_short(traceback.format_exc(), 1000))
    return "\n".join(lines)


def open_path(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(str(path))
        return f"Открыто: {path}"
    return f"Папка существует: {path}"


def retired_notice_text() -> str:
    return (
        "LocalComet Patch Panel GUI retired.\n"
        "Используй новое меню LocalComet Computer Use Core RU.\n"
        "Команды patch/test теперь доступны прямо в новом меню: выбрать patch, принять патч, тест."
    )


def run_headless_self_check() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    sample_patch = {
        "summary": "vX sample",
        "operations": [{"type": "create", "path": "tools/install_sample.py", "content": "print('ok')"}],
        "tests": ["python tools\\install_sample.py"],
    }
    ok, reason = validate_response_payload(sample_patch)
    add("response schema accepts valid patch", ok, reason)

    bad_patch = {"summary": "bad", "operations": [{"op": "create", "path": "x.py"}], "tests": ["python x.py"]}
    ok, reason = validate_response_payload(bad_patch)
    add("response schema rejects op key", not ok and "op" in reason, reason)

    success_text = "Patch успешно применен.\nPatch Registry: v6.52b записан\nSTDOUT:\n{\"failed\": 0}\nCODE: 0\n"
    add("apply detector accepts failed zero summaries", apply_output_is_success(success_text), success_text)

    failure_text = "Ошибка применения patch. Изменения ОТКАЧЕНЫ.\nCODE: 0\n"
    add("apply detector rejects rollback failure", not apply_output_is_success(failure_text), failure_text)

    nonzero_text = "Patch успешно применен.\nPatch Registry: v6.52b записан\nCODE: 1\n"
    add("apply detector rejects nonzero code", not apply_output_is_success(nonzero_text), nonzero_text)

    add("status snapshot returns text", "Project:" in refresh_status_snapshot(), "")
    add("retired notice mentions new menu", "новое меню" in retired_notice_text().lower(), "")

    source_text = _read_text(Path(__file__).resolve())
    add("no PatchPanelApp class", ("class " + "PatchPanelApp") not in source_text, "")
    add("no tkinter GUI in retired service", ("import " + "tkinter") not in source_text and ("tk." + "Tk") not in source_text, "")

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "retired_patch_panel_service_self_check",
        "version": PATCH_PANEL_VERSION,
        "summary": summary,
        "checks": checks,
    }


def _launch_new_menu() -> None:
    target = ROOT_DIR / "LocalComet_Control_Panel.py"
    if target.exists():
        os.execv(sys.executable, [sys.executable, str(target)])
    print(retired_notice_text())


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        result = run_headless_self_check()
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        raise SystemExit(0 if result.get("ok") else 1)
    if "--status" in sys.argv:
        print(refresh_status_snapshot())
        raise SystemExit(0)
    _launch_new_menu()

# BEGIN v6.57 Patch Panel UX Reliability backend bridge
PATCH_PANEL_UX_RELIABILITY_RU_V657 = "v6.57 patch panel UX reliability backend bridge installed"

try:
    _patch_panel_import_validate_apply_check_text_before_ux_ru_v657
except NameError:
    _patch_panel_import_validate_apply_check_text_before_ux_ru_v657 = import_validate_apply_check_text

try:
    _patch_panel_refresh_status_snapshot_before_ux_ru_v657
except NameError:
    _patch_panel_refresh_status_snapshot_before_ux_ru_v657 = refresh_status_snapshot

try:
    _patch_panel_run_headless_self_check_before_ux_ru_v657
except NameError:
    _patch_panel_run_headless_self_check_before_ux_ru_v657 = run_headless_self_check


def _patch_panel_ux_ru_v657():
    import importlib
    return importlib.import_module("modules.patch_panel_ux_reliability_ru")


def import_validate_apply_check_text() -> str:
    raw_text = str(_patch_panel_import_validate_apply_check_text_before_ux_ru_v657())
    try:
        ux = _patch_panel_ux_ru_v657()
        classification = ux.classify_and_report(raw_text)
        return str(classification.get("final_summary") or "") + "\n" + raw_text
    except Exception:
        return (
            "=== PATCH UX FINAL SUMMARY v6.57 ===\n"
            "❌ Ошибка formatter-а итогового статуса. Raw log сохранен ниже.\n"
            "Статус: ERROR\n"
            "Версия: v6.57\n"
            "Тесты: неизвестно\n"
            "Rollback: проверь raw log\n"
            "=== RAW LOG BELOW ===\n"
            + raw_text
        )


def refresh_status_snapshot() -> str:
    base = str(_patch_panel_refresh_status_snapshot_before_ux_ru_v657())
    try:
        ux = _patch_panel_ux_ru_v657()
        status = ux.dispatch("patch ux status")
        return base + "\npatch_panel_ux: " + json.dumps(status, ensure_ascii=True, sort_keys=True)
    except Exception as exc:
        return base + "\npatch_panel_ux: error " + str(exc)


def run_patch_panel_chat_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"статус патча", "patch status", "patch ux status", "статус patch ux"}:
        return refresh_status_snapshot()
    if lower in {"принять патч", "прими патч", "применить патч", "apply", "accept", "apply patch"}:
        return import_validate_apply_check_text()
    if lower in {"тест", "проверить проект", "проверь проект", "verify", "checks", "проверки"}:
        return run_project_checks_text()
    if lower in {"открыть reports", "reports", "open reports", "открыть отчеты", "открыть последний отчет", "open last report"}:
        try:
            ux = _patch_panel_ux_ru_v657()
            report = Path(ux._reports_dir() / "latest_patch_panel_ux_report.md")
            if report.exists() and hasattr(os, "startfile"):
                os.startfile(str(report))
                return f"Открыт последний UX отчет: {report}"
        except Exception:
            pass
        return open_path(REPORTS_DIR)
    if lower in {"открыть relay", "relay", "open relay"}:
        return open_path(RELAY_DIR)
    if lower in {"копировать итог", "copy summary", "copy final summary"}:
        try:
            ux = _patch_panel_ux_ru_v657()
            report = Path(ux._reports_dir() / "latest_patch_panel_ux_report.json")
            if report.exists():
                payload = json.loads(report.read_text(encoding="utf-8"))
                return str(payload.get("final_summary") or payload)
        except Exception as exc:
            return "STOP: не удалось прочитать итог patch UX: " + str(exc)
        return "Patch UX итог еще не найден."
    if lower.startswith(("выбрать response ", "выбери response ", "select response ", "choose response ", "response ", "source ")):
        parts = str(command).split(" ", 2)
        path_text = parts[2].strip() if len(parts) >= 3 else ""
        if lower.startswith(("response ", "source ")):
            path_text = str(command).split(" ", 1)[1].strip()
        return import_specific_response_text(Path(path_text))
    if lower in {"help", "помощь", "команды", "что умеешь", "?"}:
        return (
            "Patch Panel UX v6.57 команды:\n"
            "- выбрать response <path>\n"
            "- принять патч\n"
            "- тест\n"
            "- статус патча\n"
            "- открыть последний отчет\n"
            "- копировать итог\n"
            "- открыть relay\n"
            "- открыть reports"
        )
    return "STOP: неизвестная patch-panel команда v6.57: " + str(command)


def run_headless_self_check() -> Dict[str, Any]:
    base = _patch_panel_run_headless_self_check_before_ux_ru_v657()
    checks = list(base.get("checks", [])) if isinstance(base, dict) else []
    try:
        ux = _patch_panel_ux_ru_v657()
        ux_result = ux.run_self_check()
        checks.append({"name": "patch panel ux reliability self check", "ok": bool(ux_result.get("ok")), "details": ux_result})
        success_sample = "Patch успешно применен.\nPatch Registry: v6.57 записан\nCODE: 0\nOK: проект проверен. functional/contracts/strict green."
        checks.append({"name": "patch panel ux success summary is green", "ok": ux.classify_patch_workflow_text(success_sample).get("color") == "success", "details": ""})
        rollback_sample = "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\nCODE: 1"
        checks.append({"name": "patch panel ux rollback summary is red", "ok": ux.classify_patch_workflow_text(rollback_sample).get("status") == "ROLLED_BACK_TESTS_FAILED", "details": ""})
    except Exception:
        checks.append({"name": "patch panel ux reliability self check", "ok": False, "details": traceback.format_exc()})
    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "retired_patch_panel_service_self_check",
        "version": "v6.57",
        "summary": summary,
        "checks": checks,
    }
# END v6.57 Patch Panel UX Reliability backend bridge

# BEGIN v6.58 Developer Velocity Toolkit patch panel bridge
PATCH_PANEL_DEVELOPER_VELOCITY_BRIDGE_RU_V658 = "v6.58 developer velocity patch panel commands installed"


def _is_patch_panel_developer_velocity_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"последний сбой", "события патча", "статус разработки", "debug пакет"}


def _run_patch_panel_developer_velocity_command_ru_v658(command):
    from modules.localcomet_developer_velocity_ru import dispatch
    return dispatch(command)


try:
    _run_patch_panel_chat_command_before_developer_velocity_ru_v658
except NameError:
    _run_patch_panel_chat_command_before_developer_velocity_ru_v658 = run_patch_panel_chat_command


def run_patch_panel_chat_command(command):
    text = str(command or "").strip()
    if _is_patch_panel_developer_velocity_command_ru_v658(text):
        return _run_patch_panel_developer_velocity_command_ru_v658(text)
    if text.lower().replace("ё", "е") in {"help", "помощь", "команды", "что умеешь", "?"}:
        base = _run_patch_panel_chat_command_before_developer_velocity_ru_v658(command)
        return str(base) + "\n\nDeveloper Velocity v6.58:\n- последний сбой\n- события патча\n- статус разработки\n- debug пакет"
    return _run_patch_panel_chat_command_before_developer_velocity_ru_v658(command)

# END v6.58 Developer Velocity Toolkit patch panel bridge





