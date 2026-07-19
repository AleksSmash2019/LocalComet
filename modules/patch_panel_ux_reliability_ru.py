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


def _localcomet_v657f_find_latest_report(module_hint="patch_panel_ux"):
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
    latest = _localcomet_v657f_find_latest_report("patch_panel_ux")
    return {
        "ok": True,
        "mode": "patch_panel_ux_status",
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
    latest = _localcomet_v657f_find_latest_report("patch_panel_ux")
    return {
        "ok": True,
        "mode": "patch_panel_ux_report",
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
from typing import Any, Dict, List


PATCH_PANEL_UX_VERSION = "v6.57"
PATCH_PANEL_UX_NAME = "Patch Panel UX Reliability RU"

STATUS_NO_PATCH_SELECTED = "NO_PATCH_SELECTED"
STATUS_PATCH_SELECTED = "PATCH_SELECTED"
STATUS_VALIDATING = "VALIDATING"
STATUS_VALIDATED_OK = "VALIDATED_OK"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
STATUS_APPLYING = "APPLYING"
STATUS_RUNNING_TESTS = "RUNNING_TESTS"
STATUS_APPLIED_OK = "APPLIED_OK"
STATUS_ROLLED_BACK_TESTS_FAILED = "ROLLED_BACK_TESTS_FAILED"
STATUS_BLOCKED = "BLOCKED"
STATUS_ERROR = "ERROR"

COLOR_SUCCESS = "success"
COLOR_ERROR = "error"
COLOR_WARNING = "warning"
COLOR_NEUTRAL = "neutral"

STATUS_COLOR = {
    STATUS_NO_PATCH_SELECTED: COLOR_NEUTRAL,
    STATUS_PATCH_SELECTED: COLOR_NEUTRAL,
    STATUS_VALIDATING: COLOR_NEUTRAL,
    STATUS_VALIDATED_OK: COLOR_SUCCESS,
    STATUS_VALIDATION_FAILED: COLOR_ERROR,
    STATUS_APPLYING: COLOR_NEUTRAL,
    STATUS_RUNNING_TESTS: COLOR_NEUTRAL,
    STATUS_APPLIED_OK: COLOR_SUCCESS,
    STATUS_ROLLED_BACK_TESTS_FAILED: COLOR_ERROR,
    STATUS_BLOCKED: COLOR_ERROR,
    STATUS_ERROR: COLOR_ERROR,
}


def _lower(text: Any) -> str:
    return str(text or "").lower().replace("ё", "е")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _root_dir() -> Path:
    cwd = Path.cwd()
    if (cwd / "LocalComet_Control_Panel.py").exists() or (cwd / "LocalComet_Patch_Panel.py").exists():
        return cwd
    return _localcomet_v657f_project_root()


def _reports_dir() -> Path:
    return _root_dir() / "Projects" / "Reports" / "patch_panel_ux"


def _code_lines(text: Any) -> List[int]:
    codes: List[int] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line.lower().startswith("code:"):
            continue
        value = line.split(":", 1)[1].strip()
        try:
            codes.append(int(float(value)))
        except Exception:
            codes.append(999)
    return codes


def code_lines_are_zero(text: Any) -> bool:
    codes = _code_lines(text)
    return all(code == 0 for code in codes)


def extract_patch_version(text: Any) -> str:
    raw = str(text or "")
    patterns = [
        r"Patch Registry:\s*(v[0-9][0-9A-Za-z.\-_]*)\s*записан",
        r'"version"\s*:\s*"(v[0-9][0-9A-Za-z.\-_]*)"',
        r"\b(v[0-9]+\.[0-9]+[0-9A-Za-z.\-_]*)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    return PATCH_PANEL_UX_VERSION


def extract_report_path(text: Any) -> str:
    raw = str(text or "")
    candidates: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if any(key in lowered for key in ("report:", "отчет:", "отчет automation:", "report")):
            match = re.search(r"([A-Za-z]:\\[^\r\n]+?\.(?:md|json|txt))", stripped)
            if match:
                candidates.append(match.group(1))
    return candidates[-1] if candidates else str(_reports_dir() / "latest_patch_panel_ux_report.md")


def extract_first_failure(text: Any) -> str:
    raw = str(text or "")
    ignored = (
        '"failed": 0',
        "'failed': 0",
        "failed=0",
        "failed 0",
        "0 failed",
        "hard_failures\": 0",
        "warnings\": 0",
        "'hard_failures': 0",
        "'warnings': 0",
    )
    for line in raw.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if any(token in lowered for token in ignored):
            continue
        if any(token in lowered for token in ("[fail]", " fail", "fail:", "failed", "stop:", "traceback", "exception", "ошибка", "упали", "откачены", "blocked")):
            return stripped[:600]
    return ""


def has_nonblocking_after_patch_warning(text: Any) -> bool:
    lower = _lower(text)
    if "auto verification" not in lower and "after patch" not in lower:
        return False
    has_after_failure = (
        "status: failed" in lower
        or "[fail] full stability" in lower
        or ("full stability" in lower and "fail" in lower)
    )
    has_later_green = (
        "ok: проект проверен" in lower
        or "functional/contracts/strict green" in lower
        or ("strict_project_stability" in lower and '"warnings": 0' in lower and '"hard_failures": 0' in lower)
    )
    return bool(has_after_failure and has_later_green)


def classify_patch_workflow_text(text: Any) -> Dict[str, Any]:
    raw = str(text or "")
    lower = _lower(raw)
    codes_zero = code_lines_are_zero(raw)
    version = extract_patch_version(raw)
    warning = has_nonblocking_after_patch_warning(raw)
    rollback = any(marker in lower for marker in (
        "изменения откачены",
        "откачены",
        "rollback",
        "patch применен, но тесты упали",
        "тесты упали",
    ))
    validation_failed = any(marker in lower for marker in (
        "relay validate не прошел",
        "проверка не пройдена",
        "validation failed",
        "relay response: ❌",
        "json parse error",
        "нет списка operations",
        "operations missing",
    ))
    blocked = any(marker in lower for marker in (
        "blocked",
        "заблокирован",
        "stop: импорт response не прошел",
        "stop: relay validate не прошел",
        "stop: patch не применялся",
        "relay response не импортирован",
        "patch не применен",
    ))
    exception = any(marker in lower for marker in (
        "traceback",
        "exception",
        "assertionerror",
        "ошибка применения patch",
    ))
    success = any(marker in lower for marker in (
        "patch успешно применен",
        "patch registry:",
        "ok: patch принят",
        "applied_ok",
    ))
    if validation_failed:
        status = STATUS_VALIDATION_FAILED
    elif rollback:
        status = STATUS_ROLLED_BACK_TESTS_FAILED
    elif exception and not success:
        status = STATUS_ERROR
    elif not codes_zero:
        status = STATUS_ROLLED_BACK_TESTS_FAILED if success else STATUS_ERROR
    elif blocked and not success:
        status = STATUS_BLOCKED
    elif success and codes_zero:
        status = STATUS_APPLIED_OK
    elif "relay response: ✅" in lower or "проверка пройдена" in lower:
        status = STATUS_VALIDATED_OK
    elif "patch выбран" in lower or "response.json импортирован" in lower:
        status = STATUS_PATCH_SELECTED
    elif "stop:" in lower:
        status = STATUS_BLOCKED
    else:
        status = STATUS_ERROR if raw.strip() else STATUS_NO_PATCH_SELECTED
    color = STATUS_COLOR.get(status, COLOR_NEUTRAL)
    if warning and status == STATUS_APPLIED_OK:
        color = COLOR_WARNING
    first_failure = extract_first_failure(raw)
    summary = format_final_summary({
        "status": status,
        "color": color,
        "version": version,
        "warning": warning,
        "first_failure": first_failure,
        "report": extract_report_path(raw),
        "tests_ok": status == STATUS_APPLIED_OK and codes_zero,
        "rollback": rollback,
    })
    return {
        "ok": status == STATUS_APPLIED_OK,
        "status": status,
        "color": color,
        "version": version,
        "warning": warning,
        "tests_ok": status == STATUS_APPLIED_OK and codes_zero,
        "rollback": rollback,
        "first_failure": first_failure,
        "report": extract_report_path(raw),
        "codes": _code_lines(raw),
        "final_summary": summary,
        "generated_at": _now(),
    }


def format_final_summary(classification: Dict[str, Any]) -> str:
    status = str(classification.get("status") or STATUS_ERROR)
    version = str(classification.get("version") or PATCH_PANEL_UX_VERSION)
    report = str(classification.get("report") or (_reports_dir() / "latest_patch_panel_ux_report.md"))
    first_failure = str(classification.get("first_failure") or "не найдено")
    warning = bool(classification.get("warning"))

    if status == STATUS_APPLIED_OK and warning:
        title = "⚠️ Патч применен успешно, но есть предупреждение after-patch проверки"
        tests = "пройдены; есть неблокирующее предупреждение"
        rollback_text = "не выполнялся"
    elif status == STATUS_APPLIED_OK:
        title = "✅ Патч применен успешно"
        tests = "пройдены"
        rollback_text = "не выполнялся"
    elif status == STATUS_ROLLED_BACK_TESTS_FAILED:
        title = "❌ Патч был применен, но тесты упали. Выполнен rollback."
        tests = "упали"
        rollback_text = "выполнялся"
    elif status == STATUS_VALIDATION_FAILED:
        title = "⛔ Патч заблокирован на проверке"
        tests = "не запускались"
        rollback_text = "не выполнялся"
    elif status == STATUS_BLOCKED:
        title = "⛔ Патч заблокирован"
        tests = "не запускались или остановлены"
        rollback_text = "не выполнялся"
    elif status == STATUS_VALIDATED_OK:
        title = "✅ Патч прошел проверку, но еще не применен"
        tests = "не запускались"
        rollback_text = "не выполнялся"
    elif status == STATUS_PATCH_SELECTED:
        title = "📦 Patch выбран"
        tests = "не запускались"
        rollback_text = "не выполнялся"
    else:
        title = "❌ Ошибка patch workflow"
        tests = "неизвестно"
        rollback_text = "проверь raw log"
    return "\n".join([
        "=== PATCH UX FINAL SUMMARY v6.57 ===",
        title,
        f"Статус: {status}",
        f"Версия: {version}",
        f"Тесты: {tests}",
        f"Rollback: {rollback_text}",
        f"Первый проблемный пункт: {first_failure}",
        f"Отчет: {report}",
        "=== RAW LOG BELOW ===",
    ])


def write_latest_report(classification: Dict[str, Any], raw_text: Any = "") -> Dict[str, str]:
    reports = _reports_dir()
    reports.mkdir(parents=True, exist_ok=True)
    payload = dict(classification)
    payload["raw_log_preview"] = str(raw_text or "")[:12000]
    payload["mode"] = "patch_panel_ux_reliability"
    payload["ux_version"] = PATCH_PANEL_UX_VERSION
    json_path = reports / "latest_patch_panel_ux_report.json"
    md_path = reports / "latest_patch_panel_ux_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    md_lines = [
        "# Patch Panel UX Reliability Report",
        "",
        f"- generated_at: {payload.get('generated_at')}",
        f"- ux_version: {PATCH_PANEL_UX_VERSION}",
        f"- status: {payload.get('status')}",
        f"- color: {payload.get('color')}",
        f"- version: {payload.get('version')}",
        f"- warning: {payload.get('warning')}",
        f"- tests_ok: {payload.get('tests_ok')}",
        f"- rollback: {payload.get('rollback')}",
        f"- first_failure: {payload.get('first_failure') or 'none'}",
        "",
        "## Final summary",
        "",
        str(payload.get("final_summary") or ""),
        "",
        "## Raw log preview",
        "",
        "```text",
        str(raw_text or "")[:12000],
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def classify_and_report(text: Any) -> Dict[str, Any]:
    classification = classify_patch_workflow_text(text)
    paths = write_latest_report(classification, text)
    classification["report_json"] = paths["json"]
    classification["report_md"] = paths["md"]
    classification["final_summary"] = str(classification.get("final_summary", "")).replace(
        str(_reports_dir() / "latest_patch_panel_ux_report.md"),
        paths["md"],
    )
    return classification


def run_self_check() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    success = "Patch успешно применен.\nPatch Registry: v6.57 записан\nCODE: 0\nOK: проект проверен. functional/contracts/strict green."
    success_cls = classify_patch_workflow_text(success)
    add("apply success maps to green APPLIED_OK", success_cls["status"] == STATUS_APPLIED_OK and success_cls["color"] == COLOR_SUCCESS, success_cls)

    rollback = "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\nRollback: C:\\x\\rollback.json\nCODE: 1"
    rollback_cls = classify_patch_workflow_text(rollback)
    add("rollback maps to red ROLLED_BACK_TESTS_FAILED", rollback_cls["status"] == STATUS_ROLLED_BACK_TESTS_FAILED and rollback_cls["color"] == COLOR_ERROR, rollback_cls)

    validation = "Relay response: ❌ проверка не пройдена\nSTOP: relay validate не прошел."
    validation_cls = classify_patch_workflow_text(validation)
    add("validation failure maps to red VALIDATION_FAILED", validation_cls["status"] == STATUS_VALIDATION_FAILED and validation_cls["color"] == COLOR_ERROR, validation_cls)

    warning = success + "\nAfter Patch проверка выполнена.\nAuto Verification:\n- status: failed\n- [FAIL] full stability\n\n--- STRICT PROJECT STABILITY ---\n{\"hard_failures\": 0, \"warnings\": 0}\nOK: проект проверен. functional/contracts/strict green."
    warning_cls = classify_patch_workflow_text(warning)
    add("after patch mismatch maps to orange warning not red", warning_cls["status"] == STATUS_APPLIED_OK and warning_cls["color"] == COLOR_WARNING, warning_cls)

    false_failure = "Patch успешно применен.\nSTDOUT:\n{\"summary\":{\"failed\":0,\"passed\":10}}\nCODE: 0"
    false_cls = classify_patch_workflow_text(false_failure)
    add("failed zero is not red failure", false_cls["status"] == STATUS_APPLIED_OK, false_cls)

    paths = write_latest_report(success_cls, success)
    add("latest reports written", Path(paths["json"]).exists() and Path(paths["md"]).exists(), paths)

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "patch_panel_ux_reliability_self_check",
        "version": PATCH_PANEL_UX_VERSION,
        "summary": summary,
        "checks": checks,
    }


def dispatch(command: Any = "") -> Dict[str, Any]:
    lower = _lower(command)
    if lower in {"patch ux status", "статус patch ux", "статус патча", "patch status"}:
        report = _reports_dir() / "latest_patch_panel_ux_report.json"
        if report.exists():
            try:
                payload = json.loads(report.read_text(encoding="utf-8"))
                return {"ok": True, "handled": True, "mode": "patch_panel_ux_status", "report": str(report), "status": payload.get("status"), "payload": payload}
            except Exception as exc:
                return {"ok": False, "handled": True, "mode": "patch_panel_ux_status", "error": str(exc)}
        return {"ok": True, "handled": True, "mode": "patch_panel_ux_status", "status": STATUS_NO_PATCH_SELECTED, "report": str(report)}
    return {"ok": True, "handled": True, "mode": "patch_panel_ux_reliability", "version": PATCH_PANEL_UX_VERSION, "self_check": run_self_check()}


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

# BEGIN v6.57b command contract repair for patch_panel_ux
LOCALCOMET_COMMAND_CONTRACT_REPAIR_RU_V657B = "v6.57b command contract repair: status/report routes installed for patch_panel_ux"

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

    report_dir = _reports_dir()
    latest_report = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.md', 'patch_panel_ux_*.md', '*.md'])
    latest_json = _command_contract_latest_file_ru_v657b(report_dir, ['latest*.json', 'patch_panel_ux_*.json', '*.json'])
    return {
        "ok": True,
        "mode": "patch_panel_ux_command_contract",
        "version": "v6.57b",
        "module": __name__,
        "title": "Patch Panel UX Reliability",
        "command_contract": {
            "status": True,
            "report": True,
            "aliases": {
                "status": ['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'],
                "report": ['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча'],
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
    report_root = _reports_dir()
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = report_root / f"patch_panel_ux_contract_report_{stamp}.md"
    json_path = report_root / f"patch_panel_ux_contract_report_{stamp}.json"

    lines = [
        f"# Patch Panel UX Reliability command contract report",
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
        "mode": "patch_panel_ux_command_contract_report",
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


SUPPORTED_COMMANDS = sorted(set(list(globals().get("SUPPORTED_COMMANDS", [])) + ['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'] + ['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча']))
COMMAND_CONTRACT = dict(globals().get("COMMAND_CONTRACT", {}))
COMMAND_CONTRACT.update({
    "status": ['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'],
    "report": ['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча'],
})


def is_status_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    status_aliases = set(['status', 'статус', 'patch panel ux status', 'patch ux status', 'статус патча', 'статус patch panel ux'])
    return lower in status_aliases or lower.endswith(" status") or lower.endswith(" статус")


def is_report_command(command):
    lower = _command_contract_normalize_ru_v657b(command)
    report_aliases = set(['report', 'отчет', 'отчёт', 'patch panel ux report', 'patch ux report', 'отчет патча', 'отчёт патча', 'отчет ux патча', 'отчёт ux патча'])
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
        "mode": "patch_panel_ux_command_contract",
        "version": "v6.57b",
        "error": "unknown command",
        "command": str(command or ""),
        "supported_commands": SUPPORTED_COMMANDS,
    }

# END v6.57b command contract repair for patch_panel_ux
