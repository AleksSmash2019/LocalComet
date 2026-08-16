from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Mutation:
    mutation_id: str
    invariant: str
    rel_file: str
    old: str
    new: str
    test_command: str
    expected_reason: str
    timeout_seconds: int = 240


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(root: Path, command: str, timeout: int) -> tuple[int, str, bool]:
    try:
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", command],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, output, False
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "")
        return 124, str(out), True


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    audit = root / "AUDIT_ROOT"
    mutation_dir = audit / "mutation"
    mutation_dir.mkdir(parents=True, exist_ok=True)
    (audit / "baseline").mkdir(parents=True, exist_ok=True)
    baseline_path = audit / "baseline" / "mutation-scope.json"
    if not baseline_path.exists():
        baseline_path.write_text(json.dumps({"created_at": now(), "protocol": "15.6", "scope": "M1-M10"}, indent=2), encoding="utf-8")

    cargo_dir = root / "desktop" / "localcomet-desktop" / "src-tauri"
    mutations = [
        Mutation(
            "M1", "trust boundary", "desktop/localcomet-desktop/src-tauri/src/control_plane.rs",
            "permissions.map(|p| p.internet).unwrap_or(false)",
            "permissions.map(|p| p.internet).unwrap_or(true)",
            "cargo test assistant_context_is_trusted_typed_and_fail_closed --lib",
            "frontend/backend trust capability contract must remain deny-by-default",
        ),
        Mutation(
            "M2", "digest verification", "desktop/localcomet-desktop/src-tauri/src/approval.rs",
            "scope.input_digest.ct_eq(input_digest).unwrap_u8() != 1",
            "scope.input_digest.ct_eq(input_digest).unwrap_u8() == 1",
            "cargo test wrong_digest_rejects_without_consuming_token --lib",
            "wrong input digest must be rejected without consuming approval",
        ),
        Mutation(
            "M3", "approval single-use", "desktop/localcomet-desktop/src-tauri/src/approval.rs",
            "if consumed_at.elapsed() <= TOMBSTONE_TTL {",
            "if false {",
            "cargo test replay_is_rejected --lib",
            "replayed approval must return AlreadyConsumed",
        ),
        Mutation(
            "M4", "approval binding", "desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs",
            "if !model\n                    .compatible_runtime_ids()\n                    .iter()\n                    .any(|id| id == candidate)",
            "if false && !model\n                    .compatible_runtime_ids()\n                    .iter()\n                    .any(|id| id == candidate)",
            "cargo test runtime_start_approval_binds_explicit_runtime_id_into_digest --lib",
            "approval must bind the selected runtime_id",
        ),
        Mutation(
            "M5", "path containment", "modules/workspace_policy.py",
            "target.relative_to(self._path)",
            "target.relative_to(target)",
            "python -m pytest tools/test_v6802_bundle_security.py tools/test_workspace_memory_ru.py -q",
            "resolved target must remain inside the workspace and reject reparse/escape paths",
        ),
        Mutation(
            "M6", "bounded pipe write", "desktop/localcomet-desktop/src-tauri/src/windows_job.rs",
            "Err(error) if retryable_pipe_backpressure(&error) => {\n                if started.elapsed() >= timeout {\n                    return Err(io::Error::new(\n                        io::ErrorKind::TimedOut,\n                        \"sidecar pipe write timed out\",\n                    ));\n                }",
            "Err(error) if retryable_pipe_backpressure(&error) => {\n                if started.elapsed() >= timeout {\n                    return Ok(());\n                }",
            "cargo test bounded_writer_times_out_when_pipe_never_accepts_data --lib",
            "non-reading pipe write must hit the timeout guard, not silently succeed",
            60,
        ),
        Mutation(
            "M7", "liveness detection", "desktop/localcomet-desktop/src-tauri/src/supervisor.rs",
            "if !this.liveness_tick(policy) {",
            "if false && !this.liveness_tick(policy) {",
            "set LOCALCOMET_TEST_PROJECT_ROOT=C:\\Users\\DNS\\Documents\\LocalComet-build-week-clean&&set LOCALCOMET_TEST_PYTHON=C:\\Users\\DNS\\AppData\\Local\\Python\\bin\\python.exe&&set LOCALCOMET_REQUIRE_REAL_SIDECAR=1&&cargo test real_sidecar_liveness_restarts_after_process_kill --lib -- --nocapture",
            "killed sidecar must be detected and recovered or failed closed",
            90,
        ),
        Mutation(
            "M8", "readiness correlation", "desktop/localcomet-desktop/src-tauri/src/supervisor.rs",
            "if inner_request_id.is_empty()\n                    || outer_id != inner_request_id\n                    || reply_to != inner_request_id\n                {",
            "if inner_request_id.is_empty()\n                    || outer_id != inner_request_id\n                {",
            "cargo test p0c_ready_requires_correlated_response --lib",
            "readiness must bind both outer request and reply_to to the pending health request",
        ),
        Mutation(
            "M9", "workspace authorization", "modules/workspace_memory_ru.py",
            "        self._authorize(workspace_id, actor_id)\n        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:",
            "        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:",
            "python -m pytest tools/test_workspace_memory_ru.py -q",
            "search must reject a request for a different workspace before retrieval",
        ),
        Mutation(
            "M10", "memory deletion", "modules/workspace_memory_ru.py",
            "ids.discard(record.memory_id)",
            "pass  # mutation: leave memory index entry behind",
            "python -m pytest tools/test_workspace_memory_ru.py -q",
            "deletion must remove both record and memory index state",
        ),
    ]

    ledger: list[dict[str, object]] = []
    all_ok = True
    for m in mutations:
        path = root / m.rel_file
        original = path.read_bytes()
        original_hash = sha256_bytes(original)
        backup_path = mutation_dir / f"{m.mutation_id}.original"
        backup_path.write_bytes(original)
        text = original.decode("utf-8")
        occurrences = text.count(m.old)
        entry: dict[str, object] = {
            "mutation_id": m.mutation_id,
            "invariant": m.invariant,
            "file": m.rel_file,
            "test": m.test_command,
            "expected_reason": m.expected_reason,
            "original_sha256": original_hash,
            "original_occurrences": occurrences,
            "started_at": now(),
        }
        if occurrences == 0:
            entry.update({"status": "NOT_RUN", "reason": "exact mutation anchor not found", "rolled_back": False})
            ledger.append(entry)
            all_ok = False
            continue
        mutated_text = text.replace(m.old, m.new, 1)
        mutated = mutated_text.encode("utf-8")
        mutation_hash = sha256_bytes(mutated)
        entry["mutation_sha256"] = mutation_hash
        path.write_bytes(mutated)
        code_red, output_red, timed_out = run_command(cargo_dir if m.rel_file.startswith("desktop/localcomet-desktop/src-tauri/") else root, m.test_command, m.timeout_seconds)
        (mutation_dir / f"{m.mutation_id}.red.log").write_text(output_red, encoding="utf-8")
        entry.update({"red_exit_code": code_red, "red_timed_out": timed_out, "red_passed": code_red == 0})
        path.write_bytes(original)
        restored_hash = sha256_bytes(path.read_bytes())
        entry["restored_sha256"] = restored_hash
        entry["rollback_verified"] = restored_hash == original_hash
        if not entry["rollback_verified"]:
            entry.update({"status": "RED", "reason": "exact local rollback hash mismatch", "rolled_back": False})
            ledger.append(entry)
            all_ok = False
            break
        code_green, output_green, timed_out_green = run_command(cargo_dir if m.rel_file.startswith("desktop/localcomet-desktop/src-tauri/") else root, m.test_command, m.timeout_seconds)
        (mutation_dir / f"{m.mutation_id}.green.log").write_text(output_green, encoding="utf-8")
        entry.update({"green_exit_code": code_green, "green_timed_out": timed_out_green, "green_passed": code_green == 0, "rolled_back": True})
        if code_red == 0 or code_green != 0:
            entry["status"] = "RED"
            entry["reason"] = "mutation did not fail targeted test" if code_red == 0 else "baseline targeted test failed after rollback"
            all_ok = False
        else:
            entry["status"] = "PASS"
        entry["finished_at"] = now()
        ledger.append(entry)
        (mutation_dir / f"{m.mutation_id}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
        if not all_ok:
            break

    (mutation_dir / "mutation-ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    (mutation_dir / "mutation-ledger.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in ledger) + "\n", encoding="utf-8")
    integrity = {
        "created_at": now(),
        "protocol": "prompt-v3-15.6",
        "status": "PASS" if all_ok and len(ledger) == len(mutations) else "RED",
        "mutations_completed": len(ledger),
        "mutations_expected": len(mutations),
        "all_rollbacks_verified": all(bool(row.get("rollback_verified")) for row in ledger),
        "all_red": all(row.get("red_exit_code", 0) != 0 for row in ledger),
        "all_green_after_rollback": all(bool(row.get("green_passed")) for row in ledger),
    }
    (mutation_dir / "INTEGRITY_AFTER_MUTATION.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")
    return 0 if integrity["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

  
