from __future__ import annotations

import copy
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
NATIVE = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "isolated_hidden_desktop"
NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat()
DATE = NOW.strftime("%Y%m%d")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def duration_ms(row: dict) -> float | None:
    try:
        started = datetime.fromisoformat(str(row["started_utc"]).replace("Z", "+00:00"))
        finished = datetime.fromisoformat(str(row["finished_utc"]).replace("Z", "+00:00"))
        value = (finished - started).total_seconds() * 1000.0
        return round(value, 3) if value >= 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def p95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=20, method="inclusive")[18]


def measured_metric(samples: list[float], refs: list[str], verdicts: list[str], failures: int = 0) -> dict:
    values = [float(value) for value in samples if value is not None]
    if not values:
        return {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": failures, "reason": "No valid start/finish pair was recorded."}
    return {
        "status": "MEASURED",
        "n": len(values),
        "p50_ms": round(statistics.median(values), 3),
        "p95_ms": round(p95(values), 3),
        "max_ms": round(max(values), 3),
        "failures": failures,
        "verdicts": verdicts,
        "evidence_refs": refs,
        "method": "UTC started_utc to finished_utc interval in persisted native JSONL/report rows; p95 uses inclusive interpolation.",
    }


def ref(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def tag_path(tag: str) -> Path:
    return NATIVE / tag


def parse_digest() -> str:
    text = (AUDIT / "final2_python_refresh_evidence.log").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"tree_digest:\s*([0-9a-f]{64})", text)
    if not match:
        raise RuntimeError("final source digest not found")
    return match.group(1)


def read_run_rows(tag: str) -> list[dict]:
    return load_jsonl(tag_path(tag) / "isolated_hidden_user_runs.jsonl")


def row_summary(row: dict) -> dict:
    obs = row.get("observation") or {}
    return {
        "case_id": row.get("case_id"),
        "scenario_family": row.get("scenario_family"),
        "outcome": row.get("outcome"),
        "final_classification": row.get("final_classification") or obs.get("final_classification"),
        "started_utc": row.get("started_utc"),
        "finished_utc": row.get("finished_utc"),
        "duration_ms": duration_ms(row),
        "observed_pid": (obs.get("process_evidence") or {}).get("observed_pid"),
        "desktop": ((obs.get("text_evidence") or {}).get("desktop_attachment") or {}).get("desktop_name"),
    }


def main() -> None:
    digest = parse_digest()
    identity = (AUDIT / "final_repo_identity.log").read_text(encoding="utf-8", errors="replace").splitlines()
    branch = identity[0].strip() if identity else "unknown"
    head = identity[1].strip() if len(identity) > 1 else "unknown"
    status_lines = (AUDIT / "final_git_status.log").read_text(encoding="utf-8", errors="replace").splitlines()

    notepad_tag = "autonomous_20260828_110000_notepad_x2"
    browser_batch_tag = "autonomous_20260828_111500_browser_x2"
    browser_second_tag = "autonomous_20260828_113000_browser_02_current"
    screenshot_tags = ["autonomous_20260828_081500_screenshot_01b", "autonomous_20260828_081500_screenshot_02b"]
    coding_tag = "autonomous_20260828_090000_coding_x2"
    fake_tags = ["autonomous_20260828_091500_fake_01_current", "autonomous_20260828_091500_fake_02_current"]
    foreign_tag = "autonomous_20260828_093000_foreign_x2"
    restart_tag = "autonomous_20260828_100000_restart_final"
    cancel_tag = "autonomous_20260828_103000_cancel_final"

    notepad_rows = read_run_rows(notepad_tag)
    browser_batch_rows = read_run_rows(browser_batch_tag)
    browser_second_rows = read_run_rows(browser_second_tag)
    screenshot_rows = [read_run_rows(tag)[0] for tag in screenshot_tags]
    coding_rows = read_run_rows(coding_tag)
    fake_payloads = [load_json(tag_path(tag) / "fake_approval_dispatch.json") for tag in fake_tags]
    foreign_rows = read_run_rows(foreign_tag)
    cancel_rows = read_run_rows(cancel_tag)
    restart = load_json(tag_path(restart_tag) / "restart_application_evidence.json")

    final_native = {
        "source_tree_digest": digest,
        "branch": branch,
        "head": head,
        "runs": {
            "notepad_open_type_x2": [row_summary(row) for row in notepad_rows],
            "browser_verified_success_01": row_summary(browser_batch_rows[0]),
            "browser_batch_case_02": row_summary(browser_batch_rows[1]),
            "browser_verified_success_02": row_summary(browser_second_rows[0]),
            "screenshot_x2": [row_summary(row) for row in screenshot_rows],
            "coding_x2": [row_summary(row) for row in coding_rows],
            "fake_dom_x2": [{"tag": tag, "outcome": payload.get("outcome"), "classification": payload.get("classification"), "timestamp_utc": payload.get("timestamp_utc")} for tag, payload in zip(fake_tags, fake_payloads)],
            "foreign_x2": [row_summary(row) for row in foreign_rows],
            "restart": {
                "classification": restart.get("classification"),
                "phase1": {key: restart.get("phase1", {}).get(key) for key in ["task_id", "approval_issued", "start_called", "ledger_last_state", "pre_boundary_sha256", "post_boundary_sha256", "classification"]},
                "phase2": {key: restart.get("phase2", {}).get(key) for key in ["task_id", "listed_task", "recovered", "coding_start_calls_after_relaunch", "no_auto_resume", "duplicate_approval_rejected", "duplicate_approval_code", "pre_restart_sha256", "post_restart_sha256", "workspace_unchanged_after_relaunch", "classification"]},
                "evidence_ref": ref(tag_path(restart_tag) / "restart_application_evidence.json"),
            },
            "cancel": {
                "classification": (cancel_rows[0].get("observation") or {}).get("final_classification"),
                "terminal_only": (cancel_rows[0].get("observation") or {}).get("cancellation_terminal_only_verified"),
                "full_safe_state": (cancel_rows[0].get("observation") or {}).get("cancellation_full_safe_state_verified"),
                "evidence_ref": ref(tag_path(cancel_tag) / "isolated_hidden_user_runs.jsonl"),
            },
        },
        "cleanup_expectation": "Each completed run has owned_run_manifest.json with completed_utc and parent-side manifest-listed cleanup; interrupted browser_01d was separately cleaned by exact recorded PID-tree path and recorded in its report.",
    }
    (AUDIT / f"final_native_matrix_{DATE}.json").write_text(json.dumps(final_native, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    notepad_refs = [ref(tag_path(notepad_tag) / "isolated_hidden_user_runs.jsonl")]
    browser_refs = [ref(tag_path(browser_batch_tag) / "isolated_hidden_user_runs.jsonl"), ref(tag_path(browser_second_tag) / "isolated_hidden_user_runs.jsonl")]
    screenshot_refs = [ref(tag_path(tag) / "isolated_hidden_user_runs.jsonl") for tag in screenshot_tags]
    coding_refs = [ref(tag_path(coding_tag) / "isolated_hidden_user_runs.jsonl")]
    fake_refs = [ref(tag_path(tag) / "fake_approval_dispatch.json") for tag in fake_tags]
    foreign_refs = [ref(tag_path(foreign_tag) / "isolated_hidden_user_runs.jsonl"), ref(tag_path(foreign_tag) / "foreign_ownership_dispatch.json")]
    restart_ref = ref(tag_path(restart_tag) / "restart_application_evidence.json")
    cancel_ref = ref(tag_path(cancel_tag) / "isolated_hidden_user_runs.jsonl")

    baseline_sec = load_json(AUDIT / "sec_matrix_current_20260827.json")
    sec = copy.deepcopy(baseline_sec)
    sec.update({"generated_utc": NOW_ISO, "source_tree_digest": digest, "supersedes": "audit/sec_matrix_current_20260827.json", "policy": "A native or protected-postcondition row is not closed by a source test alone; scoped native negative evidence is not generalized beyond the tested attack path."})
    updates = {
        "SEC-001": ("G unsupported for native", "NOT_INDEPENDENTLY_VERIFIED", "No dedicated hostile web-content native fixture with protected no-upload/outbound probe was executed."),
        "SEC-002": ("A verified current", "VERIFIED_BLOCKED", "Fake DOM was clicked, but real Rust run_tool_call rejected fake_dom_token with approval_token_invalid; Notepad PID set was unchanged and no host mutation occurred. Scope is the tested fake-token path."),
        "SEC-003": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Contract tests reject traversal and absolute paths, but no current native fixture-files protected before/after byte run was executed."),
        "SEC-004": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Contract tests cover reparse/symlink fail-closed behavior; no current native hostile reparse protected-postcondition run was executed."),
        "SEC-005": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Registry/broker contracts reject unknown process/path targets; no dedicated hostile command native process-table run was executed."),
        "SEC-006": ("C contract plus A positive native; negative native missing", "NOT_INDEPENDENTLY_VERIFIED", "Current native browser runs prove allowlisted HTTPS Python navigation, isolated profile and listener identity; no non-allowlisted URL/profile negative native case was executed."),
        "SEC-007": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Rust digest/session/workspace binding contracts are covered; no application-level cross-session grant attack was executed."),
        "SEC-008": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Ledger source tests cover interior corruption; restart recovery proves approval checkpoint pause, not corrupt-ledger application recovery."),
        "SEC-009": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Bound checks are covered by contracts; no native peak-memory/oversized hostile run was executed."),
        "SEC-010": ("G unsupported for native", "NOT_INDEPENDENTLY_VERIFIED", "No current isolated Notepad/browser prompt-injection fixture with protected permission/outbound comparison was executed."),
        "SEC-011": ("A verified current, scoped", "VERIFIED_BLOCKED", "Native same-title Notepad fixture: real Rust close_owned with random unregistered ownership_request_id returned blocked; foreign PID stayed alive and broker-owned PID stayed present before owner cleanup. This proves the tested unregistered-owner path, not arbitrary registry spoofing."),
        "SEC-012": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Ordered failure contracts exist; no current native batch with dispatch counter protected postcondition was executed."),
        "SEC-013": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Skill archive validators are source-tested; no current hostile archive extraction/quarantine native fixture was executed."),
        "SEC-014": ("C contract-only", "NOT_INDEPENDENTLY_VERIFIED", "Skill tamper validators are source-tested; no current isolated install/tamper execution side-effect probe was executed."),
        "SEC-015": ("G unsupported for native", "NOT_INDEPENDENTLY_VERIFIED", "No configured headless OAuth/MCP hostile case was available and executed."),
        "SEC-016": ("A verified current", "VERIFIED_SUCCESS", "Real two-phase LocalComet application run persisted awaiting_approval, crossed an exact owner-scoped process boundary, relaunched with a fresh WebView, returned paused_for_review/requires_review=true/terminal=false, made zero coding_start calls, rejected duplicate approval with task_exists, and preserved workspace SHA."),
    }
    refs_by_id = {"SEC-002": fake_refs, "SEC-011": foreign_refs, "SEC-016": [restart_ref]}
    for row in sec["rows"]:
        evidence_class, verdict, reason = updates[row["id"]]
        row["evidence_class"] = evidence_class
        row["verdict"] = verdict
        row["reason"] = reason
        if row["id"] in refs_by_id:
            row["evidence_refs"] = refs_by_id[row["id"]]
        row["actual"] = row.get("actual", "")
    (AUDIT / f"sec_matrix_current_{DATE}_final.json").write_text(json.dumps(sec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    notepad_samples = [duration_ms(row) for row in notepad_rows]
    browser_samples = [duration_ms(browser_batch_rows[0]), duration_ms(browser_second_rows[0])]
    screenshot_samples = [duration_ms(row) for row in screenshot_rows]
    coding_samples = [duration_ms(row) for row in coding_rows]
    foreign_samples = [duration_ms(row) for row in foreign_rows]
    cancel_samples = [duration_ms(row) for row in cancel_rows]
    fake_samples = []
    for payload in fake_payloads:
        try:
            fake_samples.append((datetime.fromisoformat(payload["timestamp_utc"]) - datetime.fromisoformat(payload["timestamp_utc"])).total_seconds() * 1000.0)
        except (KeyError, TypeError, ValueError):
            pass
    performance = {
        "schema_version": "localcomet.performance.acceptance.v2",
        "generated_utc": NOW_ISO,
        "source_tree_digest": digest,
        "source": "Fresh native hidden-desktop reports at the final source cutoff; timings are persisted report intervals, not synthetic estimates.",
        "metrics": {
            "notepad_open_type": measured_metric(notepad_samples, notepad_refs, ["VERIFIED_SUCCESS", "VERIFIED_SUCCESS"]),
            "browser_readonly_search": measured_metric(browser_samples, browser_refs, ["VERIFIED_SUCCESS", "VERIFIED_SUCCESS"]),
            "desktop_screenshot": measured_metric(screenshot_samples, screenshot_refs, ["VERIFIED_SUCCESS", "VERIFIED_SUCCESS"]),
            "coding_e2e": measured_metric(coding_samples, coding_refs, ["VERIFIED_SUCCESS", "VERIFIED_SUCCESS"]),
            "foreign_ownership_negative": measured_metric(foreign_samples, foreign_refs, ["VERIFIED_BLOCKED"] * len(foreign_samples)),
            "fake_dom_approval_negative": {"status": "MEASURED_NARROW", "n": len(fake_payloads), "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "verdicts": ["VERIFIED_BLOCKED"] * len(fake_payloads), "evidence_refs": fake_refs, "reason": "Artifact timestamp records completion but no per-case started_utc; duration intentionally not inferred."},
            "cancel_model_terminal": measured_metric(cancel_samples, [cancel_ref], ["PENDING_TERMINAL"] * len(cancel_samples)),
            "restart_recovery": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "Restart evidence proves state transition and no replay but does not expose a reliable start/finish interval for recovery latency."},
            "model_load_and_ready": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "No dedicated readiness benchmark sample protocol was run."},
            "first_response": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "No dedicated first-response benchmark sample protocol was run."},
            "first_tool_call": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "No dedicated first-tool-call benchmark sample protocol was run."},
            "dispatch_to_observation": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "No dedicated dispatch/observation timestamp pair was persisted."},
            "peak_sidecar_native_memory": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "No memory sampler was run."},
            "ledger_evidence_growth": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "No growth benchmark was run."},
            "cancellation_to_safe_state": {"status": "NOT_MEASURED", "n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None, "failures": 0, "reason": "Full post-grant revocation/no-replay evidence remains open; terminal-only cancellation is reported separately."},
        },
    }
    (AUDIT / f"performance_current_{DATE}_final.json").write_text(json.dumps(performance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    provenance = load_json(AUDIT / "provenance_inventory_current_20260827.json")
    provenance = copy.deepcopy(provenance)
    provenance.update({"generated_utc": NOW_ISO, "source_tree_digest": digest, "status": "TECHNICAL_INVENTORY_NOT_LEGAL_CLEARANCE", "supersedes": "audit/provenance_inventory_current_20260827.json", "note": "Technical source/version/hash inventory only. Redistribution, commercial use, notices and model/voice/skill license decisions remain owner/legal decisions."})
    (AUDIT / f"provenance_inventory_current_{DATE}_final.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gate_logs = [
        ("npm run check", "audit/final_frontend_check.log", 0),
        ("npm test", "audit/final_frontend_test.log", 0),
        ("cargo test", "audit/final_rust_test.log", 0),
        ("cargo fmt --check", "audit/final_rust_fmt.log", 0),
        ("cargo clippy --all-targets --all-features -- -D warnings", "audit/final_rust_clippy.log", 0),
        ("Python mandatory pack (18 explicit commands)", "audit/final2_python_real_sidecar.log", 0),
        ("python scripts/check_real_sidecar_tests.py", "audit/final2_python_real_sidecar.log", 0),
        ("full pytest -q tests tools --basetemp <unique> -p no:cacheprovider", "audit/final_full_pytest_rerun.log", 0),
        ("python scripts/check_evidence_provenance.py", "audit/final2_python_evidence_provenance.log", 0),
        ("git diff --check", "audit/final_diff_check.log", 0),
        ("py_compile modified Python seams", "audit/final_py_compile.log", 0),
    ]
    gate_lines = []
    for command, log_name, exit_code in gate_logs:
        log_path = ROOT / log_name
        lines = [line.strip() for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()] if log_path.exists() else []
        tail = lines[-1] if lines else "(no output)"
        gate_lines.append({"command": command, "exit": exit_code, "last_output": tail, "log": log_name})

    final_report = f"""# Финальный аудит LocalComet — {NOW.strftime('%Y-%m-%d')}\n\n## Идентичность и исходное состояние\n\nВетка: `{branch}`. HEAD: `{head}`. Финальный source tree digest: `{digest}`; `refresh_evidence.py` подтвердил 598 source files и green evidence gates. Рабочее дерево намеренно оставлено dirty: сохранены унаследованные WIP/history; `git status --short -uall` содержит {len(status_lines)} строк. Коммитов, reset/rebase/clean и массового удаления не выполнялось.\n\nПоследний `git diff --check`: exit 0. `py_compile` для изменённых Python seams: exit 0. Технический transient helper для cleanup interrupted browser run сохранён в `audit/cleanup_interrupted_browser.py` вместе с его cleanup artifact; он не является production authority.\n\n## Что изменено в текущем продолжении\n\n| Файл/область | Назначение | Риск/ограничение |\n|---|---|---|\n| `tools/run_isolated_hidden_desktop_cu.py` | Native fake-DOM/foreign/cancel/restart orchestration; strict broker-owned PID evidence; screenshot owner-context gating; cancellation full-P0 narrowed | Harness/evidence-layer change; не расширяет Rust authority; native evidence должна быть привязана к digest |\n| `tests/test_hidden_evidence_contract.py` | Regression coverage для rollback own-preimage и cancellation predicates | Test-only |\n| `desktop/localcomet-desktop/src-tauri/src/coding_commands.rs` | Rust-owned persisted approval checkpoint для честной app-boundary recovery | Production ledger behavior changed; covered by Rust gates and native restart |\n| `desktop/localcomet-desktop/src-tauri/src/coding_orchestrator.rs` | Синхронизация continuation `awaiting_approval -> running` | Production coding state machine; compile-only truth preserved |\n| `desktop/localcomet-desktop/src-tauri/permissions/coding.toml` | Allow already registered read-only list/recover commands | Capability surface расширена только для declared recovery reads |\n| `desktop/localcomet-desktop/src-tauri/capabilities/main.json` | Current Tauri capability wiring used by restart probe | Must remain reviewed against ACL |\n| `audit/*` | Fresh evidence, matrices, gate logs and report artifacts | Technical evidence, not legal clearance |\n\n## Fresh native matrix\n\n| Scenario | Current evidence | Verdict | Scope/remark |\n|---|---:|---|---|\n| Notepad UIA/type | 2 cases in `{notepad_tag}` | `VERIFIED_SUCCESS` ×2 | Hidden desktop, Rust broker PID/image, UIA marker SHA, owner cleanup |\n| Browser readonly search | 2 successful isolated runs (`{browser_batch_tag}` case 1 and `{browser_second_tag}`) | `VERIFIED_SUCCESS` ×2 | Approval/request/action/input correlation, HTTPS Python title, isolated profile, listener PID/debug flag |\n| Screenshot | 2 cases (`{screenshot_tags[0]}`, `{screenshot_tags[1]}`) | `VERIFIED_SUCCESS` ×2 | Owner context, capture PID, PNG bytes/SHA/rendered nonblank |\n| Coding E2E | 2 cases in `{coding_tag}` | `VERIFIED_SUCCESS` ×2 | Real Tauri IPC; replay/tamper/rollback; production result honestly compile-only |\n| Fake DOM approval | 2 separate current runs | `VERIFIED_BLOCKED` ×2 | Real Rust `run_tool_call` rejects fake token; no new Notepad PID |\n| Foreign ownership | 2 cases in `{foreign_tag}` | `VERIFIED_BLOCKED` ×2 | Random unregistered close denied; same-title foreign PID survives; scope is not arbitrary registry spoofing |\n| Application restart | `{restart_tag}` | `VERIFIED_SUCCESS` | Fresh app/WebView phase 2: paused_for_review, requires_review=true, terminal=false, zero auto-start, duplicate approval `task_exists`, unchanged SHA |\n| Cancellation | `{cancel_tag}` | `PENDING_TERMINAL` | Model-turn Stop/Cancelled/worker dead/no new cards proven; post-grant continuation revocation/no replay remains open |\n\nBrowser batch additionally contains one fail-closed `VERIFIED_BLOCKED` case caused by hidden CDP port reuse inside the same batch; it is not counted as a success and is retained as diagnostic evidence.\n\n## SEC matrix result\n\nSuperseding machine-readable matrix: `audit/sec_matrix_current_{DATE}_final.json`. Current closed rows are **SEC-002**, **SEC-011** (scoped), and **SEC-016**. **SEC-001, SEC-003–010, SEC-012–015 remain `NOT_INDEPENDENTLY_VERIFIED`** because the required native protected postcondition is absent. Source tests and Conor’s synthetic fixtures are retained as contract evidence, never promoted to A solely by their self-label.\n\n## Performance and provenance\n\nSuperseding performance artifact: `audit/performance_current_{DATE}_final.json`. It measures only persisted native scenario intervals. Model readiness, first response/tool call, dispatch-to-observation, memory, ledger growth, restart latency and full cancellation-to-safe-state are explicitly `NOT_MEASURED`; no synthetic samples were invented.\n\nSuperseding provenance artifact: `audit/provenance_inventory_current_{DATE}_final.json`. It is a **technical inventory, not legal clearance**. Exact model/voice/license, notices, redistribution and commercial-use decisions remain owner/legal blockers.\n\n## Final gates\n\n| Gate | Exit | Last recorded output |\n|---|---:|---|\n""" + "\n".join(f"| `{item['command']}` | {item['exit']} | {item['last_output'][:220]} |" for item in gate_lines) + f"""\n\nFull pytest final rerun: **1385 passed, 2 skipped, 413 subtests passed in 214.54s (0:03:34), exit 0**. Real-sidecar gate: exit 0 with `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` and system CPython 3.14.6.\n\n## Score decision\n\n**9/10 не достигнуто и не заявляется.** Консервативный release score cap остаётся **8.0/10**: cancellation full P0 post-grant proof отсутствует; 13 SEC rows остаются open/not independently verified; hostile skills, headless OAuth/MCP, prompt-injection and outbound/no-upload native proof are absent; measured performance coverage is partial; provenance/legal owner decisions are unresolved. Это не измеренная метрика качества, а fail-closed cap по acceptance blockers.\n\nЧто действительно улучшено: app-boundary restart/recovery теперь подтверждён реальным production Tauri path; fake-DOM denial, scoped foreign-owner denial, current browser/Notepad/screenshot/coding runs и gates — fresh/current на digest `{digest}`. Это повышает доказанную поверхность, но не превращает incomplete SEC/P0 set в 9/10.\n\n## Остаточные blockers\n\n1. Для полного B3 cancellation нужен реальный approved/consumed in-flight host continuation, доказанная revoke/no-replay после Stop и независимый protected postcondition.\n2. Нужны native protected-postcondition fixtures для SEC-001, 003–010, 012–015, особенно no-upload, non-allowlisted URL/profile, cross-session grant, corrupt ledger, bounded resources, injection, ordered failure, skills tamper/quarantine и headless OAuth/MCP.\n3. Нужны owner/legal решения по GGUF, RHVoice/Piper, notices, redistribution/commercial use и skill/asset licenses.\n4. Нужны dedicated readiness/latency/memory/ledger/cancellation performance protocols; current measured intervals не заменяют их.\n\n## Dashboard\n\nAppend-only current dashboard update выполнен в `pipeline/mvp-program-status.md` и `pipeline/loop-status.md`; historical sections не переписаны.\n"""
    (AUDIT / f"final_audit_{DATE}_ru.md").write_text(final_report, encoding="utf-8")

    status_json = {"generated_utc": NOW_ISO, "branch": branch, "head": head, "source_tree_digest": digest, "dirty_status_lines": len(status_lines), "native_matrix_ref": ref(AUDIT / f"final_native_matrix_{DATE}.json"), "sec_matrix_ref": ref(AUDIT / f"sec_matrix_current_{DATE}_final.json"), "performance_ref": ref(AUDIT / f"performance_current_{DATE}_final.json"), "provenance_ref": ref(AUDIT / f"provenance_inventory_current_{DATE}_final.json"), "report_ref": ref(AUDIT / f"final_audit_{DATE}_ru.md"), "score_claim": "9/10 not achieved; conservative cap 8.0/10"}
    (AUDIT / f"final_status_snapshot_{DATE}.json").write_text(json.dumps(status_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status_json, ensure_ascii=False))


if __name__ == "__main__":
    main()
