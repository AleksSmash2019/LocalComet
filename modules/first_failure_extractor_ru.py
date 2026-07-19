from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional


FIRST_FAILURE_EXTRACTOR_VERSION = "v6.58"
FIRST_FAILURE_EXTRACTOR_NAME = "LocalComet First Failure Extractor RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists() or (candidate / "LocalComet_Control_Panel.py").exists():
            return candidate
    return get_project_root()


def _reports_dir() -> Path:
    return _root() / "Projects" / "Reports"


def _output_dir() -> Path:
    path = _reports_dir() / "developer_velocity"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_text(path: Path, limit: int = 250000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > limit:
        return text[: limit // 2] + "\n[... middle trimmed ...]\n" + text[-limit // 2 :]
    return text


def _candidate_logs() -> List[Path]:
    root = _root()
    bases = [
        root / "Projects" / "Reports" / "patch_panel_ux",
        root / "Projects" / "Reports" / "strict_project_stability",
        root / "Projects" / "Reports" / "localcomet_functional_tests",
        root / "Projects" / "Reports" / "computer_use_contracts",
        root / "Projects" / "ChatGPTRelay",
        root / "Projects" / "SelfEdit",
    ]
    patterns = ["latest*.md", "latest*.json", "*.md", "*.json", "*.txt", "*.log"]
    seen: Dict[str, Path] = {}
    for base in bases:
        if not base.exists():
            continue
        for pattern in patterns:
            for item in base.glob(pattern):
                if item.is_file():
                    try:
                        seen[str(item.resolve())] = item
                    except Exception:
                        seen[str(item)] = item
    return sorted(seen.values(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:80]


def _line_score(line: str) -> int:
    lower = line.lower().replace("ё", "е")
    score = 0
    high = [
        "traceback",
        "assertionerror",
        "filenotfounderror",
        "modulenotfounderror",
        "syntaxerror",
        "typeerror",
        "valueerror",
        "oserror",
        "exception",
        "code: 1",
        "code: 2",
        "code: 999",
        "rollback",
        "откачен",
        "тесты упали",
        "validation failed",
        "проверка не пройдена",
        "ошибка применения",
        "stop:",
    ]
    medium = ["fail", "failed", "hard_failures", "warnings", "blocked", "error", "ошибка", "упали"]
    for token in high:
        if token in lower:
            score += 100
    for token in medium:
        if token in lower:
            score += 20
    if re.search(r"\bCODE:\s*[1-9]\d*\b", line, re.IGNORECASE):
        score += 150
    return score


def _extract_from_text(text: str, source: str = "") -> Dict[str, Any]:
    lines = str(text or "").splitlines()
    best: Optional[Dict[str, Any]] = None
    for index, line in enumerate(lines):
        score = _line_score(line)
        if score <= 0:
            continue
        start = max(0, index - 3)
        end = min(len(lines), index + 8)
        context = "\n".join(lines[start:end]).strip()
        item = {
            "found": True,
            "source": source,
            "line_number": index + 1,
            "score": score,
            "first_error": line.strip()[:1000],
            "context": context[:5000],
        }
        if best is None or item["score"] > best["score"]:
            best = item
    if best:
        code_match = re.search(r"\bCODE:\s*([0-9]+)", best.get("context", ""), re.IGNORECASE)
        if code_match:
            best["code"] = int(code_match.group(1))
        return best
    return {
        "found": False,
        "source": source,
        "first_error": "",
        "context": "",
        "line_number": 0,
        "score": 0,
    }


def extract_first_failure_from_text(text: str, source: str = "text") -> Dict[str, Any]:
    payload = _extract_from_text(text, source=source)
    payload.update({
        "ok": True,
        "mode": "first_failure_from_text",
        "version": FIRST_FAILURE_EXTRACTOR_VERSION,
        "generated_at": _now(),
    })
    return payload


def find_latest_failure(write_report: bool = True) -> Dict[str, Any]:
    candidates = _candidate_logs()
    best: Optional[Dict[str, Any]] = None
    inspected: List[str] = []
    for path in candidates:
        inspected.append(str(path))
        text = _read_text(path)
        item = _extract_from_text(text, source=str(path))
        if item.get("found") and (best is None or int(item.get("score", 0)) > int(best.get("score", 0))):
            best = item
    if best is None:
        best = {
            "found": False,
            "source": "",
            "first_error": "",
            "context": "",
            "line_number": 0,
            "score": 0,
        }
    payload: Dict[str, Any] = {
        "ok": True,
        "mode": "first_failure_extractor",
        "version": FIRST_FAILURE_EXTRACTOR_VERSION,
        "generated_at": _now(),
        "failure": best,
        "inspected_count": len(inspected),
        "inspected": inspected[:25],
        "report": "",
        "json": "",
    }
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _output_dir()
    json_path = out / f"first_failure_{_stamp()}.json"
    md_path = out / f"first_failure_{_stamp()}.md"
    latest_json = out / "latest_first_failure.json"
    latest_md = out / "latest_first_failure.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    failure = payload.get("failure", {})
    lines = [
        "# LocalComet First Failure",
        "",
        f"- version: {payload.get('version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- found: {failure.get('found')}",
        f"- source: {failure.get('source')}",
        f"- line: {failure.get('line_number')}",
        "",
        "## First error",
        "",
        "```text",
        str(failure.get("first_error", "")),
        "```",
        "",
        "## Context",
        "",
        "```text",
        str(failure.get("context", "")),
        "```",
    ]
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path, "latest_json": latest_json, "latest_md": latest_md}


def status(command: str = "status") -> Dict[str, Any]:
    latest = _output_dir() / "latest_first_failure.json"
    return {
        "ok": True,
        "mode": "first_failure_extractor_status",
        "version": FIRST_FAILURE_EXTRACTOR_VERSION,
        "latest_json": str(latest),
        "latest_exists": latest.exists(),
        "commands": ["последний сбой", "last failure", "first failure"],
    }


def report(command: str = "report") -> Dict[str, Any]:
    return find_latest_failure(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"последний сбой", "последняя ошибка", "first failure", "last failure", "latest failure"}:
        result = find_latest_failure(write_report=True)
        result["handled"] = True
        return result
    if lower in {"status", "статус", "first failure status"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет", "first failure report"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "first_failure_extractor", "reason": "unknown command"}
