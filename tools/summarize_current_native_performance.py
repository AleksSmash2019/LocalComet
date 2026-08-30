from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "isolated_hidden_desktop"
OUTPUT = ROOT / "audit" / "performance_current_20260827.json"
RUNS = {
    "browser_readonly_search": [
        "nine_20260827_browser_python_32",
        "nine_20260827_browser_python_33",
    ],
    "notepad_open_type": [
        "nine_20260827_notepad_open_type_11",
        "nine_20260827_notepad_open_type_12",
    ],
    "desktop_screenshot": [
        "nine_20260827_screenshot_12",
        "nine_20260827_screenshot_13",
    ],
    "cancel_browser_diagnostic": ["nine_20260827_cancel_browser_01"],
}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty sample")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def read_row(tag: str) -> dict:
    path = REPORT_ROOT / tag / "isolated_hidden_user_runs.jsonl"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"expected one row in {path}, got {len(lines)}")
    return json.loads(lines[0])


def main() -> None:
    metrics: dict[str, dict] = {}
    for metric, tags in RUNS.items():
        samples_ms: list[float] = []
        failures = 0
        refs: list[str] = []
        verdicts: list[str] = []
        for tag in tags:
            row = read_row(tag)
            started = parse_time(row["started_utc"])
            finished = parse_time(row["finished_utc"])
            samples_ms.append((finished - started).total_seconds() * 1000.0)
            verdict = row.get("final_classification", "")
            verdicts.append(verdict)
            if verdict != "VERIFIED_SUCCESS":
                failures += 1
            refs.append(str((REPORT_ROOT / tag / "isolated_hidden_user_runs.jsonl").relative_to(ROOT)))
        metrics[metric] = {
            "status": "MEASURED_FROM_PERSISTED_RUN_TIMESTAMPS",
            "n": len(samples_ms),
            "p50_ms": round(percentile(samples_ms, 0.50), 3),
            "p95_ms": round(percentile(samples_ms, 0.95), 3),
            "max_ms": round(max(samples_ms), 3),
            "failures": failures,
            "verdicts": verdicts,
            "evidence_refs": refs,
        }
    for metric in (
        "model_load_and_ready",
        "first_response",
        "first_tool_call",
        "dispatch_to_observation",
        "restart_recovery",
        "peak_sidecar_native_memory",
        "ledger_evidence_growth",
        "cancellation_to_safe_state",
    ):
        metrics[metric] = {
            "status": "NOT_MEASURED",
            "n": 0,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
            "failures": None,
            "reason": "No authoritative current-tree sample with the required probe was executed.",
        }
    OUTPUT.write_text(
        json.dumps(
            {
                "schema_version": "localcomet.performance.evidence.v1",
                "generated_utc": "2026-08-27",
                "source": "persisted native harness started_utc/finished_utc only",
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
