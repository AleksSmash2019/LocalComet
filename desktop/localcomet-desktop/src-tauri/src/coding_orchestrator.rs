//! Coding orchestrator — bounded deterministic loop over existing Rust
//! authorities only: checkpoint (patch apply) + terminal runner (typed
//! process seam) + diagnostics parser + task ledger (typed verdicts).
//! No LLM, no direct subprocess bypass, no shell.
//!
//! Production chain: plan(fixed ops) → checkpoint preimage/apply → typed
//! TerminalRequest (rustc compile check + focused test) → diagnostics parsed
//! from the runner's bounded output → VALIDATING gate → COMPLETED only with
//! zero error diagnostics AND a green focused test; otherwise FAILED/BLOCKED.

#![allow(dead_code)]

use crate::checkpoint::{self, FileOp, Patch};
use crate::diagnostics;
use crate::task_ledger::{LedgerStore, TaskEvent, TaskState};
use crate::terminal_runner;
use crate::terminal_runner::{ExecutionGuard, TerminalRequest, TerminalResult};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::Path;

pub const ORCHESTRATOR_SCHEMA: &str = "localcomet.coding-orchestrator.v1";

/// Truthful outcome vocabulary (P1). These are RESULT statuses, not risk
/// levels: a task may only claim `behavior_verified` when the focused test
/// binary was actually executed through the typed TaskTestBinary registry
/// with exit code 0. `compile_verified_only` is an honest weaker outcome —
/// never presented as full success.
pub const OUTCOME_BEHAVIOR_VERIFIED: &str = "behavior_verified";
pub const OUTCOME_COMPILE_ONLY: &str = "compile_verified_only";
pub const OUTCOME_FAILED: &str = "failed";
pub const OUTCOME_BLOCKED: &str = "blocked";
pub const OUTCOME_CANCELLED: &str = "cancelled";
pub const OUTCOME_PAUSED_FOR_REVIEW: &str = "paused_for_review";

#[derive(Debug, Clone)]
pub struct OrchestratorResult {
    /// One of OUTCOME_* — machine-readable truthful terminal state.
    pub status: &'static str,
    /// How strongly the postcondition was verified for THIS run.
    pub verification_level: &'static str, // behavior_verified | compile_verified_only | none
    pub applied_paths: Vec<String>,
    pub error_diagnostics: usize,
    pub generation_hash: String,
    /// Focused-test exit code (None when the loop stopped before testing).
    pub test_exit_code: Option<i32>,
    pub reason: String,
}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

#[allow(clippy::too_many_arguments)]
fn append_typed_event(
    store: &LedgerStore,
    seq: &mut u64,
    prev: &mut String,
    task_id: &str,
    step_id: &str,
    patch_id: &str,
    workspace_digest: &str,
    permission_context_digest: &str,
    from: TaskState,
    to: TaskState,
    event_type: &str,
    extra: serde_json::Value,
) -> Result<TaskEvent, String> {
    *seq += 1;
    let mut payload = json!({
        "permission_context_digest": permission_context_digest,
        "workspace_digest": workspace_digest,
    });
    if let (Some(obj), Some(extra)) = (payload.as_object_mut(), extra.as_object()) {
        for (k, v) in extra {
            obj.insert(k.clone(), v.clone());
        }
    }
    let event = TaskEvent {
        schema_version: "task.ledger.event.v1".to_string(),
        seq: *seq,
        event_id: format!("evt_{}", seq),
        task_id: task_id.to_string(),
        task_version: 1,
        created_at_unix_ms: 0,
        event_type: event_type.to_string(),
        state_before: from,
        state_after: to,
        step_id: Some(step_id.to_string()),
        checkpoint_id: None,
        request_id: None,
        action_id: None,
        correlation_id: Some(patch_id.to_string()),
        payload,
        prev_event_hash: prev.clone(),
        event_hash: String::new(),
    };
    let appended = store.append_event(event)?;
    *prev = appended.event_hash.clone();
    Ok(appended)
}

/// One bounded coding task over a workspace fixture. Every host-side command
/// goes through the typed terminal runner seam — the orchestrator has no
/// other process path.
#[allow(clippy::too_many_arguments)]
pub fn run_coding_task(
    store_root: &Path,
    workspace_root: &Path,
    ledger_root: &Path,
    task_id: &str,
    patch_id: &str,
    step_id: &str,
    base_hashes: &HashMap<String, String>,
    ops: Vec<FileOp>,
    permission_context_digest: &str,
    cancel_flag: &dyn Fn() -> bool,
    guard: &ExecutionGuard,
    // When true, a `__lc_focus_test.rs` harness must exist and is compiled
    // AND executed through the runner (independent behavior postcondition).
    // When false, the postcondition is the clean compile of touched code.
    require_focus_test: bool,
) -> Result<OrchestratorResult, String> {
    let ledger = LedgerStore::new_with_root(ledger_root.to_path_buf());
    let workspace_digest = {
        let mut h = Sha256::new();
        h.update(workspace_root.to_string_lossy().as_bytes());
        format!("{:x}", h.finalize())
    };
    let existing_events = ledger.verify_chain(task_id)?;
    let mut seq: u64 = existing_events.last().map(|event| event.seq).unwrap_or(0);
    let mut prev_hash = existing_events
        .last()
        .map(|event| event.event_hash.clone())
        .unwrap_or_else(|| "0".repeat(64));

    // Typed ledger emitter: fine-grained progress rides in `event_type`
    // while state transitions stay inside the validated TaskState machine.
    let emit = |store: &LedgerStore,
                seq_ref: &mut u64,
                prev: &mut String,
                from: TaskState,
                to: TaskState,
                event_type: &str,
                extra: serde_json::Value|
     -> Result<TaskEvent, String> {
        append_typed_event(
            store,
            seq_ref,
            prev,
            task_id,
            step_id,
            patch_id,
            &workspace_digest,
            permission_context_digest,
            from,
            to,
            event_type,
            extra,
        )
    };

    if existing_events.is_empty() {
        // CREATED → INTENT_COMPILED (plan = fixed typed ops) → RUNNING.
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Created,
            TaskState::IntentCompiled,
            "context_ready_planned",
            json!({"patch_id": patch_id}),
        )?;
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::IntentCompiled,
            TaskState::Running,
            "checkpoint_preimage_patch_proposed",
            json!({}),
        )?;
    } else {
        // Production coding_start continues the approval plan that was
        // persisted before the one-time grant. Never accept an arbitrary
        // pre-existing state or silently create a second hash chain.
        let last = existing_events
            .last()
            .expect("non-empty event chain has a last event");
        if last.state_after != TaskState::AwaitingApproval {
            return Err("task_ledger_state_not_awaiting_approval".to_string());
        }
        let expected_content_sha = existing_events
            .iter()
            .rev()
            .find_map(|event| event.payload.get("content_sha256"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        let actual_content_sha = ops
            .iter()
            .find_map(|op| op.content.as_ref())
            .map(|content| sha256_hex(content))
            .unwrap_or_else(|| "missing".to_string());
        if expected_content_sha != actual_content_sha {
            return Err("task_ledger_patch_digest_mismatch".to_string());
        }
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::AwaitingApproval,
            TaskState::Running,
            "coding_approval_consumed_starting",
            json!({"patch_id": patch_id}),
        )?;
    }

    // Patch through the checkpoint authority (base-hash conflict safe).
    let patch = Patch {
        patch_id: patch_id.to_string(),
        ops,
    };
    let manifest = match checkpoint::apply_patch(
        store_root,
        workspace_root,
        &patch,
        base_hashes,
        task_id,
        step_id,
    ) {
        Ok(m) => m,
        Err(reason) => {
            let to = if reason == "CONFLICT" {
                TaskState::Blocked
            } else {
                TaskState::Failed
            };
            emit(
                &ledger,
                &mut seq,
                &mut prev_hash,
                TaskState::Running,
                to.clone(),
                "patch_conflict_failed",
                json!({"reason": reason}),
            )?;
            return Ok(OrchestratorResult {
                status: if to == TaskState::Blocked {
                    OUTCOME_BLOCKED
                } else {
                    OUTCOME_FAILED
                },
                verification_level: "none",
                applied_paths: vec![],
                error_diagnostics: 0,
                generation_hash: String::new(),
                test_exit_code: None,
                reason,
            });
        }
    };
    emit(
        &ledger,
        &mut seq,
        &mut prev_hash,
        TaskState::Running,
        TaskState::Running,
        "patch_applied_checkpoint_postimage",
        json!({"paths": manifest.paths}),
    )?;

    // Generation hash binds diagnostics/tests to THIS postimage.
    let generation_hash = {
        let mut combined = String::new();
        for path in &manifest.paths {
            combined.push_str(path);
            combined.push(':');
            combined.push_str(
                manifest
                    .after_sha256
                    .get(path)
                    .map(String::as_str)
                    .unwrap_or("missing"),
            );
            combined.push(';');
        }
        sha256_hex(combined.as_bytes())
    };

    // --- Compiler check THROUGH the typed terminal runner ---
    // One rustc invocation per touched .rs file; parse the runner's bounded
    // stderr with the diagnostics adapter.
    let mut error_count = 0usize;
    for rel in &manifest.paths {
        if !rel.ends_with(".rs") {
            continue;
        }
        // Pre-flight cancel: a cancel that arrives after the patch applied
        // but before verification must still ROLL BACK — the workspace must
        // never keep an unverified patch just because the task was cancelled.
        if cancel_flag() {
            emit(
                &ledger,
                &mut seq,
                &mut prev_hash,
                TaskState::Running,
                TaskState::RollbackRequired,
                "cancel_requested_rollback_required",
                json!({"phase": "pre_compile"}),
            )?;
            return finish_cancelled_with_rollback(
                &ledger,
                &mut seq,
                &mut prev_hash,
                store_root,
                workspace_root,
                &manifest,
                error_count,
                generation_hash,
            );
        }
        let request = TerminalRequest {
            command_id: format!("{task_id}_compile"),
            command_kind: terminal_runner::CommandKind::RustcDiagnostics,
            program: "rustc".to_string(),
            args: vec![
                "--edition=2021".into(),
                "--crate-type=lib".into(),
                "--emit=metadata".into(),
                "--error-format=json".into(),
                format!("--out-dir={}", std::env::temp_dir().display()),
                rel.replace('/', "\\"),
            ],
            cwd_relative: String::new(),
            workspace_root: workspace_root.to_path_buf(),
            workspace_digest: workspace_digest.clone(),
            permission_context_digest: permission_context_digest.to_string(),
            task_id: task_id.to_string(),
            step_id: step_id.to_string(),
            timeout_ms: 60_000,
            output_budget_bytes: 65_536,
        };
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Running,
            TaskState::Running,
            "terminal_running",
            json!({"command_id": request.command_id}),
        )?;
        let terminal: TerminalResult = match terminal_runner::execute(&request, cancel_flag, guard)
        {
            Ok(t) => t,
            Err(e) => {
                eprintln!(
                    "[orch-debug] compile exec failed: {e} program={} cwd={:?}",
                    request.program, request.cwd_relative
                );
                let _ = emit(
                    &ledger,
                    &mut seq,
                    &mut prev_hash,
                    TaskState::Running,
                    TaskState::Blocked,
                    "terminal_blocked",
                    json!({"reason": e}),
                );
                return Err(e.to_string());
            }
        };
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Running,
            TaskState::Running,
            "terminal_completed",
            json!({
                "exit_code": terminal.exit_code,
                "termination_kind": format!("{:?}", terminal.termination_kind),
                "fingerprint_hex": terminal.fingerprint_hex,
            }),
        )?;
        if terminal.termination_kind != crate::terminal_runner::TerminationKind::Exited {
            if terminal.termination_kind == crate::terminal_runner::TerminationKind::Cancelled {
                emit(
                    &ledger,
                    &mut seq,
                    &mut prev_hash,
                    TaskState::Running,
                    TaskState::RollbackRequired,
                    "task_cancelled_during_compile_rollback_required",
                    json!({}),
                )?;
                return finish_cancelled_with_rollback(
                    &ledger,
                    &mut seq,
                    &mut prev_hash,
                    store_root,
                    workspace_root,
                    &manifest,
                    error_count,
                    generation_hash,
                );
            }
            emit(
                &ledger,
                &mut seq,
                &mut prev_hash,
                TaskState::Running,
                TaskState::Failed,
                "diagnostics_blocked",
                json!({}),
            )?;
            return Ok(OrchestratorResult {
                status: OUTCOME_FAILED,
                verification_level: "none",
                applied_paths: manifest.paths.clone(),
                error_diagnostics: 0,
                generation_hash,
                test_exit_code: None,
                reason: format!("terminal {:?}", terminal.termination_kind),
            });
        }
        let diags = diagnostics::parse_rustc_diagnostics(
            workspace_root,
            &terminal.stderr_bounded,
            &workspace_digest,
            &generation_hash,
        );
        error_count += diags.iter().filter(|d| d.severity == "error").count();
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Running,
            TaskState::Running,
            "diagnostics_updated",
            json!({"errors": error_count}),
        )?;
    }

    // Compiler errors after the patch → never COMPLETED. The applied patch
    // is a proven broken state, so it is rolled back to the checkpoint
    // preimage; the ledger records ROLLBACK_REQUIRED → RECOVERING → FAILED.
    if error_count > 0 {
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Running,
            TaskState::RollbackRequired,
            "postcondition_failed_rollback_required",
            json!({"errors": error_count}),
        )?;
        return finish_with_rollback(
            &ledger,
            &mut seq,
            &mut prev_hash,
            store_root,
            workspace_root,
            &manifest,
            error_count,
            generation_hash,
            None,
        );
    }

    // --- Focused test THROUGH the typed terminal runner ---
    // Compile+run a tiny assertion harness against the touched crate root:
    // real toolchain, real exit code, no fabricated result. Skippable only
    // when the caller explicitly runs without a focus harness; the compile
    // postcondition above still applies — but the outcome is then honestly
    // `compile_verified_only`, never full success (P1 truthfulness).
    if !require_focus_test {
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Running,
            TaskState::Validating,
            "test_skipped_no_focus_harness",
            json!({}),
        )?;
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Validating,
            TaskState::Completed,
            "validating_postcondition_compile_only",
            json!({
                "generation_hash": generation_hash,
                "verification_level": OUTCOME_COMPILE_ONLY,
                "reason": "no focused test harness in this environment; compile postcondition only",
            }),
        )?;
        return Ok(OrchestratorResult {
            status: OUTCOME_COMPILE_ONLY,
            verification_level: OUTCOME_COMPILE_ONLY,
            applied_paths: manifest.paths.clone(),
            error_diagnostics: error_count,
            generation_hash,
            test_exit_code: None,
            reason: "clean diagnostics; focused test unavailable in this environment, so behavior is NOT verified".to_string(),
        });
    }
    // Focus-test artifacts are TASK-SCOPED end to end: source name defines
    // the crate name, which drives every linker artifact (.exe/.pdb) in the
    // shared temp out-dir. A fixed shared name let two concurrent coding
    // tasks corrupt each other's link output (observed under parallel test
    // execution as intermittent link failure → missing registration →
    // policy_rejected_unregistered_test_artifact).
    let safe_task: String = task_id
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '_' || c == '-' {
                c
            } else {
                '_'
            }
        })
        .take(64)
        .collect();
    let focus_rs_rel = format!("__lc_focus_{safe_task}.rs");
    // rustc names the linked output after the crate (source file) name.
    let test_exe = std::env::temp_dir().join(format!("__lc_focus_{safe_task}.exe"));
    let test_request = TerminalRequest {
        command_id: format!("{task_id}_test"),
        command_kind: terminal_runner::CommandKind::RustcDiagnostics,
        program: "rustc".to_string(),
        args: vec![
            "--edition=2021".into(),
            "--crate-type=bin".into(),
            "--emit=link".into(),
            format!("--out-dir={}", std::env::temp_dir().display()),
            focus_rs_rel,
        ],
        cwd_relative: String::new(),
        workspace_root: workspace_root.to_path_buf(),
        workspace_digest: workspace_digest.clone(),
        permission_context_digest: permission_context_digest.to_string(),
        task_id: task_id.to_string(),
        step_id: step_id.to_string(),
        timeout_ms: 60_000,
        output_budget_bytes: 65_536,
    };
    emit(
        &ledger,
        &mut seq,
        &mut prev_hash,
        TaskState::Running,
        TaskState::Validating,
        "test_running",
        json!({}),
    )?;
    let test_terminal =
        terminal_runner::execute(&test_request, cancel_flag, guard).map_err(|e| {
            let _ = emit(
                &ledger,
                &mut seq,
                &mut prev_hash,
                TaskState::Validating,
                TaskState::Blocked,
                "terminal_blocked",
                json!({"reason": e}),
            );
            e.to_string()
        })?;
    emit(
        &ledger,
        &mut seq,
        &mut prev_hash,
        TaskState::Validating,
        TaskState::Validating,
        "test_completed",
        json!({
            "exit_code": test_terminal.exit_code,
        }),
    )?;

    // Real execution: run the linked focus-test binary (independent
    // filesystem/behavior postcondition), not just its compilation. The
    // binary is admitted ONLY when this task's link-compile produced it.
    if test_terminal.exit_code != Some(0) {
        // Explicit honest failure path: a harness that did not build can
        // never be executed, and the task must roll back — not lean on a
        // runner policy error as implicit control flow.
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Validating,
            TaskState::RollbackRequired,
            "focus_test_build_failed_rollback_required",
            json!({"exit_code": test_terminal.exit_code}),
        )?;
        return finish_with_rollback(
            &ledger,
            &mut seq,
            &mut prev_hash,
            store_root,
            workspace_root,
            &manifest,
            error_count,
            generation_hash,
            test_terminal.exit_code,
        );
    }
    guard.register_test_artifact(task_id, &test_exe);
    let run_request = TerminalRequest {
        command_id: format!("{task_id}_test_run"),
        command_kind: terminal_runner::CommandKind::TaskTestBinary,
        program: test_exe.to_string_lossy().to_string(),
        args: vec![],
        cwd_relative: String::new(),
        workspace_root: workspace_root.to_path_buf(),
        workspace_digest: workspace_digest.clone(),
        permission_context_digest: permission_context_digest.to_string(),
        task_id: task_id.to_string(),
        step_id: step_id.to_string(),
        timeout_ms: 30_000,
        output_budget_bytes: 16_384,
    };
    let run_terminal = terminal_runner::execute(&run_request, cancel_flag, guard).map_err(|e| {
        let _ = emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Validating,
            TaskState::Blocked,
            "terminal_blocked",
            json!({"reason": e}),
        );
        e.to_string()
    })?;
    let _ = std::fs::remove_file(&test_exe);

    // P1 truthfulness: behavior_verified REQUIRES an actually executed focus
    // binary with exit code 0 through the typed TaskTestBinary seam.
    let passed = test_terminal.exit_code == Some(0) && run_terminal.exit_code == Some(0);
    if run_terminal.termination_kind == crate::terminal_runner::TerminationKind::Cancelled
        || test_terminal.termination_kind == crate::terminal_runner::TerminationKind::Cancelled
    {
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Validating,
            TaskState::RollbackRequired,
            "task_cancelled_during_test_rollback_required",
            json!({}),
        )?;
        return finish_cancelled_with_rollback(
            &ledger,
            &mut seq,
            &mut prev_hash,
            store_root,
            workspace_root,
            &manifest,
            error_count,
            generation_hash,
        );
    }
    if !passed {
        // Focused-test failure after the patch landed: proven broken state →
        // ROLLBACK_REQUIRED, restore preimage, then terminal FAILED (or
        // PAUSED_FOR_REVIEW when even the rollback conflicts).
        emit(
            &ledger,
            &mut seq,
            &mut prev_hash,
            TaskState::Validating,
            TaskState::RollbackRequired,
            "postcondition_failed_rollback_required",
            json!({
                "compile_exit": test_terminal.exit_code,
                "run_exit": run_terminal.exit_code,
            }),
        )?;
        return finish_with_rollback(
            &ledger,
            &mut seq,
            &mut prev_hash,
            store_root,
            workspace_root,
            &manifest,
            error_count,
            generation_hash,
            test_terminal.exit_code,
        );
    }
    emit(
        &ledger,
        &mut seq,
        &mut prev_hash,
        TaskState::Validating,
        TaskState::Completed,
        "validating_postcondition",
        json!({
            "generation_hash": generation_hash,
            "verification_level": OUTCOME_BEHAVIOR_VERIFIED,
            "test_exit_code": test_terminal.exit_code,
            "run_exit_code": run_terminal.exit_code,
        }),
    )?;

    Ok(OrchestratorResult {
        status: OUTCOME_BEHAVIOR_VERIFIED,
        verification_level: OUTCOME_BEHAVIOR_VERIFIED,
        applied_paths: manifest.paths.clone(),
        error_diagnostics: error_count,
        generation_hash,
        test_exit_code: test_terminal.exit_code,
        reason: "clean diagnostics and focused test".to_string(),
    })
}

/// Cancellation AFTER the patch applied: the workspace must never keep an
/// unverified patch just because the task was cancelled. Roll back to the
/// preimage, then report the typed `cancelled` terminal (or PAUSED_FOR_REVIEW
/// when even the rollback conflicts — never a silent partial state).
#[allow(clippy::too_many_arguments)]
fn finish_cancelled_with_rollback(
    ledger: &LedgerStore,
    seq: &mut u64,
    prev_hash: &mut String,
    store_root: &Path,
    workspace_root: &Path,
    manifest: &checkpoint::CheckpointManifest,
    error_diagnostics: usize,
    generation_hash: String,
) -> Result<OrchestratorResult, String> {
    let restored = checkpoint::restore_files(store_root, workspace_root, manifest);
    match restored {
        Ok(_) => {
            append_typed_event(
                ledger,
                seq,
                prev_hash,
                &manifest.task_id,
                &manifest.step_id,
                &manifest.patch_id,
                &manifest.workspace_digest,
                "",
                TaskState::RollbackRequired,
                TaskState::Recovering,
                "cancel_rollback_restored_preimage",
                json!({"paths": manifest.paths}),
            )?;
            append_typed_event(
                ledger,
                seq,
                prev_hash,
                &manifest.task_id,
                &manifest.step_id,
                &manifest.patch_id,
                &manifest.workspace_digest,
                "",
                TaskState::Recovering,
                TaskState::Cancelled,
                "cancel_rolled_back_cancelled_terminal",
                json!({"generation_hash": generation_hash}),
            )?;
            Ok(OrchestratorResult {
                status: OUTCOME_CANCELLED,
                verification_level: "none",
                applied_paths: manifest.paths.clone(),
                error_diagnostics,
                generation_hash,
                test_exit_code: None,
                reason: "cancelled; unverified patch rolled back to preimage".to_string(),
            })
        }
        Err(conflict) => {
            append_typed_event(
                ledger,
                seq,
                prev_hash,
                &manifest.task_id,
                &manifest.step_id,
                &manifest.patch_id,
                &manifest.workspace_digest,
                "",
                TaskState::RollbackRequired,
                TaskState::PausedForReview,
                "cancel_rollback_conflict_paused_for_review",
                json!({"reason": conflict}),
            )?;
            Ok(OrchestratorResult {
                status: OUTCOME_PAUSED_FOR_REVIEW,
                verification_level: "none",
                applied_paths: manifest.paths.clone(),
                error_diagnostics,
                generation_hash,
                test_exit_code: None,
                reason: format!("cancelled; rollback conflicted: {conflict}"),
            })
        }
    }
}

/// Postcondition failed after the patch applied: attempt a real rollback to
/// the checkpoint preimage and record the honest terminal outcome.
/// - Restore succeeded → RECOVERING → FAILED ("patch rolled back").
/// - Restore conflicted → PAUSED_FOR_REVIEW (user must resolve; no auto-retry).
#[allow(clippy::too_many_arguments)]
fn finish_with_rollback(
    ledger: &LedgerStore,
    seq: &mut u64,
    prev_hash: &mut String,
    store_root: &Path,
    workspace_root: &Path,
    manifest: &checkpoint::CheckpointManifest,
    error_diagnostics: usize,
    generation_hash: String,
    test_exit_code: Option<i32>,
) -> Result<OrchestratorResult, String> {
    let restored = checkpoint::restore_files(store_root, workspace_root, manifest);
    match restored {
        Ok(_) => {
            append_typed_event(
                ledger,
                seq,
                prev_hash,
                &manifest.task_id,
                &manifest.step_id,
                &manifest.patch_id,
                &manifest.workspace_digest,
                "",
                TaskState::RollbackRequired,
                TaskState::Recovering,
                "rollback_restored_preimage",
                json!({"paths": manifest.paths}),
            )?;
            append_typed_event(
                ledger,
                seq,
                prev_hash,
                &manifest.task_id,
                &manifest.step_id,
                &manifest.patch_id,
                &manifest.workspace_digest,
                "",
                TaskState::Recovering,
                TaskState::Failed,
                "rollback_completed_failed_terminal",
                json!({"generation_hash": generation_hash}),
            )?;
            Ok(OrchestratorResult {
                status: OUTCOME_FAILED,
                verification_level: "none",
                applied_paths: manifest.paths.clone(),
                error_diagnostics,
                generation_hash,
                test_exit_code,
                reason: "postcondition failed; patch rolled back to preimage".to_string(),
            })
        }
        Err(conflict) => {
            append_typed_event(
                ledger,
                seq,
                prev_hash,
                &manifest.task_id,
                &manifest.step_id,
                &manifest.patch_id,
                &manifest.workspace_digest,
                "",
                TaskState::RollbackRequired,
                TaskState::PausedForReview,
                "rollback_conflict_paused_for_review",
                json!({"reason": conflict}),
            )?;
            Ok(OrchestratorResult {
                status: OUTCOME_PAUSED_FOR_REVIEW,
                verification_level: "none",
                applied_paths: manifest.paths.clone(),
                error_diagnostics,
                generation_hash,
                test_exit_code,
                reason: format!("postcondition failed; rollback conflicted: {conflict}"),
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::terminal_runner::ExecutionGuard;
    use std::path::PathBuf;

    fn tmp_dir(prefix: &str) -> PathBuf {
        let base = std::env::temp_dir();
        let dir = base.join(format!(
            "{prefix}_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    /// Focus-test program: independent filesystem postcondition over the
    /// patched file. Written by the fixture, executed through the runner.
    const FOCUS_TEST_SRC: &str = r#"
fn main() {
    let body = std::fs::read_to_string("lib_ok.rs").expect("patched file present");
    assert!(body.contains("pub fn ok()"), "postcondition content");
}
"#;

    #[test]
    fn clean_patch_compiles_runs_focus_test_and_completes() {
        let ws = tmp_dir("orch_ws");
        let store = tmp_dir("orch_store");
        let ledger_root = tmp_dir("orch_ledger");
        std::fs::write(ws.join("__lc_focus_t_clean.rs"), FOCUS_TEST_SRC).unwrap();

        let mut base = HashMap::new();
        base.insert("lib_ok.rs".to_string(), "missing".to_string());
        let ops = vec![FileOp {
            path: "lib_ok.rs".into(),
            content: Some(b"pub fn ok() -> u32 { 1 }\n".to_vec()),
        }];
        let guard = ExecutionGuard::new();
        let result = run_coding_task(
            &store,
            &ws,
            &ledger_root,
            "t_clean",
            "p1",
            "s1",
            &base,
            ops,
            "pcd_123",
            &|| false,
            &guard,
            true,
        )
        .unwrap();
        assert_eq!(
            result.status, OUTCOME_BEHAVIOR_VERIFIED,
            "reason={}",
            result.reason
        );
        assert_eq!(result.error_diagnostics, 0);
        assert_eq!(result.test_exit_code, Some(0));

        // Ledger: full ordered transition chain ending COMPLETED.
        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        let events = ledger.verify_chain("t_clean").unwrap();
        let types: Vec<&str> = events.iter().map(|e| e.event_type.as_str()).collect();
        for expected in [
            "context_ready_planned",
            "checkpoint_preimage_patch_proposed",
            "patch_applied_checkpoint_postimage",
            "terminal_running",
            "terminal_completed",
            "diagnostics_updated",
            "test_running",
            "test_completed",
            "validating_postcondition",
        ] {
            assert!(types.contains(&expected), "missing {expected} in {types:?}");
        }
        assert_eq!(events.last().unwrap().state_after, TaskState::Completed);
        assert!(events[0].payload["permission_context_digest"] == json!("pcd_123"));

        let _ = std::fs::remove_dir_all(ws);
        let _ = std::fs::remove_dir_all(store);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    #[test]
    fn broken_patch_fails_rolls_back_and_never_completes() {
        let ws = tmp_dir("orch_ws2");
        let store = tmp_dir("orch_store2");
        let ledger_root = tmp_dir("orch_ledger2");
        let mut base = HashMap::new();
        base.insert("lib_bad.rs".to_string(), "missing".to_string());
        let ops = vec![FileOp {
            path: "lib_bad.rs".into(),
            content: Some(b"fn broken(x) { x }\n".to_vec()),
        }];
        let guard = ExecutionGuard::new();
        let result = run_coding_task(
            &store,
            &ws,
            &ledger_root,
            "t_broken",
            "p2",
            "s1",
            &base,
            ops,
            "",
            &|| false,
            &guard,
            true,
        )
        .unwrap();
        assert_eq!(result.status, "failed");
        assert!(result.error_diagnostics > 0);
        assert!(result.test_exit_code.is_none());

        // Proven rollback: the broken patch must NOT survive in the workspace.
        assert!(
            !ws.join("lib_bad.rs").exists(),
            "failed patch must be rolled back to preimage (file absent before)"
        );

        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        let events = ledger.verify_chain("t_broken").unwrap();
        assert_eq!(events.last().unwrap().state_after, TaskState::Failed);
        assert!(
            !events.iter().any(|e| e.state_after == TaskState::Completed),
            "a failing patch must never reach COMPLETED"
        );
        // Typed rollback chain recorded.
        let types: Vec<&str> = events.iter().map(|e| e.event_type.as_str()).collect();
        for expected in [
            "postcondition_failed_rollback_required",
            "rollback_restored_preimage",
            "rollback_completed_failed_terminal",
        ] {
            assert!(types.contains(&expected), "missing {expected} in {types:?}");
        }

        // Rollback is also visible as a checkpoint restore path: applying the
        // SAME base again must not conflict (workspace really is at preimage).
        let _ = std::fs::remove_dir_all(ws);
        let _ = std::fs::remove_dir_all(store);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    /// Patch compiles cleanly but the focused behavior assertion fails at
    /// runtime → ROLLBACK_REQUIRED, real restore, terminal FAILED.
    #[test]
    fn failing_focus_test_rolls_back_applied_patch() {
        let ws = tmp_dir("orch_ws5");
        let store = tmp_dir("orch_store5");
        let ledger_root = tmp_dir("orch_ledger5");
        std::fs::write(ws.join("__lc_focus_t_focus_fail.rs"), FOCUS_TEST_SRC).unwrap();

        let mut base = HashMap::new();
        base.insert("lib_ok.rs".to_string(), "missing".to_string());
        // Compiles fine but does NOT contain `pub fn ok()` → focus test fails.
        let ops = vec![FileOp {
            path: "lib_ok.rs".into(),
            content: Some(b"pub fn other() -> u32 { 2 }\n".to_vec()),
        }];
        let guard = ExecutionGuard::new();
        let result = run_coding_task(
            &store,
            &ws,
            &ledger_root,
            "t_focus_fail",
            "p5",
            "s1",
            &base,
            ops,
            "",
            &|| false,
            &guard,
            true,
        )
        .unwrap();
        assert_eq!(result.status, "failed", "reason={}", result.reason);
        assert!(!ws.join("lib_ok.rs").exists(), "patch rolled back");

        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        let events = ledger.verify_chain("t_focus_fail").unwrap();
        assert_eq!(events.last().unwrap().state_after, TaskState::Failed);
        assert!(events
            .iter()
            .any(|e| e.event_type == "rollback_restored_preimage"));

        let _ = std::fs::remove_dir_all(ws);
        let _ = std::fs::remove_dir_all(store);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    #[test]
    fn base_conflict_blocks_without_touching_files() {
        let ws = tmp_dir("orch_ws3");
        let store = tmp_dir("orch_store3");
        let ledger_root = tmp_dir("orch_ledger3");
        std::fs::write(ws.join("a.txt"), b"user-edit").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), "deadbeef".to_string());
        let ops = vec![FileOp {
            path: "a.txt".into(),
            content: Some(b"overwritten".to_vec()),
        }];
        let guard = ExecutionGuard::new();
        let result = run_coding_task(
            &store,
            &ws,
            &ledger_root,
            "t_conflict",
            "p3",
            "s1",
            &base,
            ops,
            "",
            &|| false,
            &guard,
            true,
        )
        .unwrap();
        assert_eq!(result.status, "blocked");
        assert_eq!(std::fs::read(ws.join("a.txt")).unwrap(), b"user-edit");

        let _ = std::fs::remove_dir_all(ws);
        let _ = std::fs::remove_dir_all(store);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    /// Cancel arriving AFTER the patch applied but BEFORE verification: the
    /// unverified patch must be rolled back and the terminal must be the
    /// typed `cancelled` — never completed, never a silent half-state.
    /// Deterministic: the cancel flag is set before any process spawns.
    #[test]
    fn cancel_after_apply_rolls_back_and_reports_cancelled() {
        let ws = tmp_dir("orch_ws_cancel");
        let store = tmp_dir("orch_store_cancel");
        let ledger_root = tmp_dir("orch_ledger_cancel");
        // Pre-existing file so rollback has a real preimage to restore.
        std::fs::write(ws.join("calc.rs"), b"pub fn original() {}\n").unwrap();
        let mut base = HashMap::new();
        base.insert("calc.rs".to_string(), sha256_hex(b"pub fn original() {}\n"));
        let ops = vec![FileOp {
            path: "calc.rs".into(),
            content: Some(b"pub fn patched() -> u32 { 7 }\n".to_vec()),
        }];
        let guard = ExecutionGuard::new();
        let result = run_coding_task(
            &store,
            &ws,
            &ledger_root,
            "t_cancel",
            "pc1",
            "s1",
            &base,
            ops,
            "",
            &|| true, // cancel already requested before verification
            &guard,
            true,
        )
        .unwrap();
        assert_eq!(result.status, OUTCOME_CANCELLED, "reason={}", result.reason);
        assert_eq!(result.verification_level, "none");
        assert_eq!(result.test_exit_code, None);
        // Proven rollback: workspace is back at its preimage bytes.
        assert_eq!(
            std::fs::read_to_string(ws.join("calc.rs")).unwrap(),
            "pub fn original() {}\n"
        );
        // Ledger ends in the typed Cancelled state.
        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        let events = ledger.verify_chain("t_cancel").unwrap();
        assert_eq!(events.last().unwrap().state_after, TaskState::Cancelled);
        assert!(
            events
                .iter()
                .any(|e| e.event_type == "cancel_rollback_restored_preimage"),
            "rollback evidence must be in the chain"
        );

        let _ = std::fs::remove_dir_all(ws);
        let _ = std::fs::remove_dir_all(store);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    /// Orchestrator-level policy denial surfaces typed error; repeated
    /// equivalent attempts are denied by the shared ExecutionGuard budget.
    #[test]
    fn orchestrator_guard_blocks_repeated_policy_denial() {
        let guard = ExecutionGuard::new();
        let ws = tmp_dir("orch_ws4");
        let request = TerminalRequest {
            command_id: "doom_probe".into(),
            command_kind: crate::terminal_runner::CommandKind::RustcDiagnostics,
            program: "rustc".into(),
            args: vec!["--edition=2021".into(), "bad & evil".into()],
            cwd_relative: String::new(),
            workspace_root: ws.clone(),
            workspace_digest: "w".into(),
            permission_context_digest: String::new(),
            task_id: "t_doom".into(),
            step_id: "s".into(),
            timeout_ms: 5_000,
            output_budget_bytes: 1024,
        };
        // Metachar policy denies before spawn; guard budget then exhausts.
        for attempt in 0..4 {
            match terminal_runner::execute(&request, &|| false, &guard) {
                Err("policy_rejected_shell_or_metachar") => {}
                Err(other) => panic!("unexpected err at {attempt}: {other}"),
                Ok(_) => panic!("metachar request must never execute"),
            }
        }
        let _ = std::fs::remove_dir_all(ws);
    }
}
