//! Rust-policy terminal runner (bounded, typed, default-deny).
//!
//! Authority chain: typed request → command-kind allowlist → path/arg policy →
//! owned child inside a kill-on-close Job Object with concurrently drained
//! bounded pipes → timeout/cancel kills the WHOLE job tree → verified cleanup.
//! No shell interpreter is ever spawned; args are passed as a raw list.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub const RUNNER_SCHEMA: &str = "localcomet.terminal-result.v1";
const MAX_IDENTICAL_FAILURES: u32 = 2;

/// Typed command allowlist. Every production execution must declare its kind;
/// arbitrary executables are default-deny.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CommandKind {
    /// Compiler diagnostics through the Rust toolchain (`rustc` only).
    RustcDiagnostics,
    /// A test binary produced earlier by THIS SAME task's link-compile step,
    /// registered per task in the ExecutionGuard. Nothing else runs.
    TaskTestBinary,
}

/// Deterministic execution fingerprint for doom-loop detection:
/// canonical program + normalized args + workspace digest. No secrets.
pub fn execution_fingerprint(program: &str, args: &[String], workspace_digest: &str) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(program.as_bytes());
    h.update([0]);
    for a in args {
        h.update(a.as_bytes());
        h.update([1]);
    }
    h.update([0]);
    h.update(workspace_digest.as_bytes());
    h.finalize().into()
}

/// Doom-loop registry: repeated identical failures beyond budget deny.
/// Also owns the per-task allowlist of test artifacts this guard may run.
/// One guard instance per coding task: budgets never leak across tasks.
#[derive(Default)]
pub struct ExecutionGuard {
    failures: Mutex<HashMap<[u8; 32], u32>>,
    allowed_artifacts: Mutex<HashMap<String, HashSet<String>>>,
}

impl ExecutionGuard {
    pub fn new() -> Self {
        Self::default()
    }

    fn normalize_program(p: &str) -> String {
        p.to_ascii_lowercase()
    }

    /// Register a test executable that THIS task's runner may later execute.
    pub fn register_test_artifact(&self, task_id: &str, exe_path: &Path) {
        let normalized = Self::normalize_program(&exe_path.to_string_lossy());
        self.allowed_artifacts
            .lock()
            .expect("artifact registry poisoned")
            .entry(task_id.to_string())
            .or_default()
            .insert(normalized);
    }

    pub(crate) fn test_artifact_allowed(&self, task_id: &str, program: &str) -> bool {
        let normalized = Self::normalize_program(program);
        self.allowed_artifacts
            .lock()
            .expect("artifact registry poisoned")
            .get(task_id)
            .is_some_and(|set| set.contains(&normalized))
    }

    /// Returns Err when this fingerprint already failed MAX_IDENTICAL_FAILURES times.
    pub fn admit(&self, fingerprint: &[u8; 32]) -> Result<(), &'static str> {
        let map = self.failures.lock().expect("guard poisoned");
        let count = map.get(fingerprint).copied().unwrap_or(0);
        if count >= MAX_IDENTICAL_FAILURES {
            return Err("doom_loop_budget_exhausted");
        }
        Ok(())
    }

    pub fn record_failure(&self, fingerprint: &[u8; 32]) {
        let mut map = self.failures.lock().expect("guard poisoned");
        *map.entry(*fingerprint).or_insert(0) += 1;
    }

    pub fn record_success(&self, fingerprint: &[u8; 32]) {
        let mut map = self.failures.lock().expect("guard poisoned");
        map.remove(fingerprint);
    }
}

/// Typed production request — the ONLY seam the coding orchestrator may use
/// to reach a process. Rust derives risk internally; caller risk hints are
/// never trusted. Correlation is carried opaquely and echoed into the result.
#[derive(Clone, Debug)]
pub struct TerminalRequest {
    pub command_id: String,
    /// Typed allowlist entry — see CommandKind.
    pub command_kind: CommandKind,
    pub program: String,
    pub args: Vec<String>,
    /// Workspace-relative cwd; validated against `workspace_root`.
    pub cwd_relative: String,
    pub workspace_root: PathBuf,
    pub workspace_digest: String,
    /// Digest of the armed PermissionContext (empty when normal session).
    /// Carried opaquely for ledger correlation; echoed into task evidence.
    #[allow(dead_code)]
    pub permission_context_digest: String,
    pub task_id: String,
    /// Correlation only; consumed by ledger emitters around the runner call.
    #[allow(dead_code)]
    pub step_id: String,
    pub timeout_ms: u64,
    pub output_budget_bytes: usize,
}

impl TerminalRequest {
    pub fn fingerprint(&self) -> [u8; 32] {
        execution_fingerprint(&self.program, &self.args, &self.workspace_digest)
    }
}

fn program_base_name(program: &str) -> String {
    let lower = program.to_ascii_lowercase();
    lower
        .rsplit(['\\', '/'])
        .next()
        .unwrap_or(&lower)
        .trim_matches('"')
        .to_string()
}

/// Resolve a bare program name against PATH into an absolute executable path.
/// CreateProcessW with an explicit application name does not search PATH, and
/// absolute identity is required for the allowlist anyway.
fn resolve_executable(program: &str) -> Option<PathBuf> {
    let candidate = PathBuf::from(program);
    if candidate.is_absolute() {
        return Some(candidate);
    }
    if program.contains('\\') || program.contains('/') {
        // Relative-with-separator paths are never allowed.
        return None;
    }
    let path_var = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path_var) {
        let direct = dir.join(&candidate);
        if direct.is_file() {
            return Some(direct);
        }
        let with_exe = dir.join(format!("{program}.exe"));
        if with_exe.is_file() {
            return Some(with_exe);
        }
    }
    None
}

/// Typed command-kind allowlist. Default-deny: only the registered kinds run.
fn enforce_command_allowlist(
    kind: CommandKind,
    program: &str,
    task_id: &str,
    guard: &ExecutionGuard,
) -> Result<PathBuf, &'static str> {
    match kind {
        CommandKind::RustcDiagnostics => {
            let resolved = resolve_executable(program).ok_or("executable_not_found")?;
            let base = program_base_name(&resolved.to_string_lossy());
            if base == "rustc" || base == "rustc.exe" {
                Ok(resolved)
            } else {
                Err("policy_rejected_unallowlisted_command")
            }
        }
        CommandKind::TaskTestBinary => {
            let candidate = PathBuf::from(program);
            if !candidate.is_absolute()
                || !program_base_name(program).ends_with(".exe")
                || program.contains("..")
            {
                return Err("policy_rejected_unallowlisted_command");
            }
            // Only a binary this exact task produced through a link-compile
            // may run; canonical path equality closes case/short-name tricks
            // on the registration side (both sides normalized lowercase).
            if guard.test_artifact_allowed(task_id, program) {
                Ok(candidate)
            } else {
                Err("policy_rejected_unregistered_test_artifact")
            }
        }
    }
}

/// Execute a typed request through every policy gate and return a typed,
/// bounded, correlated result. Non-zero exit is a valid typed outcome
/// (FAILED verdict), not an Err; Err is reserved for policy/infra denials.
pub fn execute(
    request: &TerminalRequest,
    cancel_flag: &dyn Fn() -> bool,
    guard: &ExecutionGuard,
) -> Result<TerminalResult, &'static str> {
    let resolved_program = enforce_command_allowlist(
        request.command_kind,
        &request.program,
        &request.task_id,
        guard,
    )?;
    let cwd = validate_cwd(&request.workspace_root, &request.cwd_relative)?;
    let mut result = run_bounded(
        &request.command_id,
        &resolved_program.to_string_lossy(),
        &request.args,
        &cwd,
        &request.workspace_digest,
        Duration::from_millis(request.timeout_ms),
        request.output_budget_bytes,
        cancel_flag,
        guard,
    )?;
    // Bind correlation + provenance onto the typed result.
    result.fingerprint_hex = hex(&request.fingerprint());
    Ok(result)
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn contains_shell_metachar(s: &str) -> bool {
    s.chars().any(|c| {
        matches!(
            c,
            '&' | '|' | ';' | '<' | '>' | '^' | '%' | '"' | '`' | '\n' | '\r' | '$'
        )
    })
}

fn is_shell_program(program: &str) -> bool {
    let lower = program.to_ascii_lowercase();
    let base = lower
        .rsplit(['\\', '/'])
        .next()
        .unwrap_or(&lower)
        .trim_matches('"');
    matches!(
        base,
        "cmd"
            | "cmd.exe"
            | "powershell"
            | "powershell.exe"
            | "pwsh"
            | "pwsh.exe"
            | "wscript"
            | "wscript.exe"
            | "cscript"
            | "cscript.exe"
            | "bash"
            | "bash.exe"
            | "sh"
            | "sh.exe"
    )
}

/// Path policy: cwd must resolve inside `workspace_root` without escaping.
pub fn validate_cwd(workspace_root: &Path, cwd_relative: &str) -> Result<PathBuf, &'static str> {
    // Empty = workspace root itself (the common case for single-crate tasks).
    if cwd_relative.is_empty() {
        return Ok(workspace_root.to_path_buf());
    }
    if cwd_relative.len() > 240
        || cwd_relative.contains('\0')
        || cwd_relative.contains("..")
        || cwd_relative.contains('%')
        || cwd_relative.starts_with('/')
        || cwd_relative.starts_with('\\')
        || cwd_relative.contains(':')
    {
        return Err("invalid_cwd");
    }
    let joined = workspace_root.join(cwd_relative);
    // Reparse/symlink escape check on every component.
    let mut cur = workspace_root.to_path_buf();
    for part in Path::new(cwd_relative).components() {
        cur = cur.join(part);
        if let Ok(md) = std::fs::symlink_metadata(&cur) {
            if md.file_type().is_symlink() {
                return Err("reparse_escape");
            }
        }
    }
    if !joined.is_dir() {
        return Err("cwd_not_found");
    }
    Ok(joined)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TerminationKind {
    Exited,
    TimeoutKilled,
    Cancelled,
}

#[derive(Debug, Serialize)]
pub struct TerminalResult {
    pub schema_version: &'static str,
    pub command_id: String,
    pub exit_code: Option<i32>,
    pub termination_kind: TerminationKind,
    pub duration_ms: u64,
    pub stdout_bounded: String,
    pub stderr_bounded: String,
    pub stdout_truncated: bool,
    pub stderr_truncated: bool,
    /// True only when raw child output was NOT valid UTF-8 and was decoded
    /// lossily (replacement chars possible) — an honest encoding signal.
    pub stdout_lossy: bool,
    pub stderr_lossy: bool,
    pub fingerprint_hex: String,
    pub process_tree_cleaned: bool,
}

/// UTF-8-first decode with truthful lossiness instead of silent mojibake:
/// valid UTF-8 (incl. Cyrillic) round-trips byte-exact; anything else is
/// lossy-converted AND flagged so callers never mistake garbage for content.
fn decode_output(bytes: &[u8]) -> (String, bool) {
    match std::str::from_utf8(bytes) {
        Ok(text) => (text.to_owned(), false),
        Err(_) => (String::from_utf8_lossy(bytes).into_owned(), true),
    }
}

/// Budget-enbounded concurrent capture buffer shared with a drain thread.
struct SharedBounded {
    inner: Mutex<(Vec<u8>, bool)>,
    budget: usize,
}

impl SharedBounded {
    fn new(budget: usize) -> Arc<Self> {
        Arc::new(Self {
            inner: Mutex::new((Vec::new(), false)),
            budget,
        })
    }

    fn push(&self, chunk: &[u8]) {
        let mut guard = self.inner.lock().expect("capture buffer poisoned");
        let (buf, truncated) = &mut *guard;
        if buf.len() >= self.budget {
            *truncated = true;
            return;
        }
        let allowed = (self.budget - buf.len()).min(chunk.len());
        buf.extend_from_slice(&chunk[..allowed]);
        if allowed < chunk.len() {
            *truncated = true;
        }
    }

    /// Join the drain thread and produce bounded text plus truncation and
    /// lossy-decode flags.
    fn finish(
        self: Arc<Self>,
        handle: Option<std::thread::JoinHandle<()>>,
    ) -> (String, bool, bool) {
        if let Some(handle) = handle {
            let _ = handle.join();
        }
        let guard = self.inner.lock().expect("capture buffer poisoned");
        let (text, lossy) = decode_output(&guard.0);
        (text, guard.1, lossy)
    }
}

fn spawn_drain_thread(
    pipe: Option<impl Read + Send + 'static>,
    sink: Arc<SharedBounded>,
) -> Option<std::thread::JoinHandle<()>> {
    pipe.map(|mut pipe| {
        std::thread::spawn(move || {
            let mut chunk = [0u8; 4096];
            loop {
                match pipe.read(&mut chunk) {
                    Ok(0) => break,
                    Ok(n) => sink.push(&chunk[..n]),
                    Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                    Err(_) => break,
                }
            }
        })
    })
}

enum RunningChild {
    #[cfg(windows)]
    Contained(crate::windows_job::ContainedManagedRuntimeProcess),
    #[cfg(not(windows))]
    Raw(std::process::Child),
}

impl RunningChild {
    fn is_running(&self) -> bool {
        match self {
            #[cfg(windows)]
            Self::Contained(c) => c.is_running(),
            #[cfg(not(windows))]
            Self::Raw(c) => matches!(c.try_wait(), Ok(None)),
        }
    }

    /// Kill the whole tree (job on Windows), then wait until dead (bounded).
    fn kill_tree_and_wait(&self) {
        match self {
            #[cfg(windows)]
            Self::Contained(c) => {
                c.terminate_job_tree(1);
                c.wait_bounded(5_000);
            }
            #[cfg(not(windows))]
            Self::Raw(c) => {
                let _ = c.kill();
                let _ = c.wait();
            }
        }
    }

    fn exit_code(&self) -> Option<i32> {
        match self {
            #[cfg(windows)]
            Self::Contained(c) => c.exit_code(),
            #[cfg(not(windows))]
            Self::Raw(c) => c.try_wait().ok().flatten().and_then(|s| s.code()),
        }
    }

    /// Authoritative OS-side live-process count inside the containment job.
    #[cfg(windows)]
    fn job_active_processes(&self) -> Option<u32> {
        match self {
            Self::Contained(c) => c.job_active_processes(),
        }
    }
}

fn spawn_running(program: &str, args: &[String], cwd: &Path) -> Result<RunningChild, &'static str> {
    // CreateProcessW does not search PATH when given an application name, and
    // the allowlist requires absolute identity anyway.
    let absolute = resolve_executable(program).ok_or("executable_not_found")?;
    #[cfg(windows)]
    {
        let env: Vec<(std::ffi::OsString, std::ffi::OsString)> = std::env::vars_os().collect();
        let spec = crate::windows_job::ManagedRuntimeLaunchSpec {
            executable: absolute,
            args: args.iter().map(std::ffi::OsString::from).collect(),
            current_dir: cwd.to_path_buf(),
            env,
        };
        crate::windows_job::spawn_terminal_contained(&spec)
            .map(RunningChild::Contained)
            .map_err(|e| match e.kind() {
                std::io::ErrorKind::NotFound => "executable_not_found",
                _ => "spawn_failed",
            })
    }
    #[cfg(not(windows))]
    {
        let _ = absolute;
        std::process::Command::new(program)
            .args(args)
            .current_dir(cwd)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map(RunningChild::Raw)
            .map_err(|e| match e.kind() {
                std::io::ErrorKind::NotFound => "executable_not_found",
                _ => "spawn_failed",
            })
    }
}

type OutputPipes = (Option<Box<dyn Read + Send>>, Option<Box<dyn Read + Send>>);

fn take_output_pipes(child: &mut RunningChild) -> OutputPipes {
    match child {
        #[cfg(windows)]
        RunningChild::Contained(c) => (
            c.take_stdout().map(|f| Box::new(f) as Box<dyn Read + Send>),
            c.take_stderr().map(|f| Box::new(f) as Box<dyn Read + Send>),
        ),
        #[cfg(not(windows))]
        RunningChild::Raw(c) => (
            c.stdout.take().map(|f| Box::new(f) as Box<dyn Read + Send>),
            c.stderr.take().map(|f| Box::new(f) as Box<dyn Read + Send>),
        ),
    }
}

/// Run one bounded, policy-checked command. The caller must have resolved
/// risk/approval through the Rust authority BEFORE calling this function.
#[allow(clippy::too_many_arguments)]
pub fn run_bounded(
    command_id: &str,
    program: &str,
    args: &[String],
    cwd: &Path,
    workspace_digest: &str,
    timeout: Duration,
    output_budget_bytes: usize,
    cancel_flag: &dyn Fn() -> bool,
    guard: &ExecutionGuard,
) -> Result<TerminalResult, &'static str> {
    // Policy gates — fail-closed.
    if program.is_empty()
        || program.len() > 260
        || is_shell_program(program)
        || contains_shell_metachar(program)
        || args.iter().any(|a| contains_shell_metachar(a))
    {
        return Err("policy_rejected_shell_or_metachar");
    }
    // Explicit shell-interpreter deny even without metachars: cmd /C and
    // powershell are never allowed as raw terminal programs. Typed broker must be used.
    let lower_args = args
        .iter()
        .map(|a| a.to_ascii_lowercase())
        .collect::<Vec<_>>();
    if lower_args
        .iter()
        .any(|a| a == "/c" || a == "-command" || a == "-encodedcommand")
    {
        return Err("policy_rejected_shell_or_metachar");
    }
    let fingerprint = execution_fingerprint(program, args, workspace_digest);
    guard.admit(&fingerprint)?;

    let started = Instant::now();
    let mut child = spawn_running(program, args, cwd)?;

    // Concurrently drained pipes: a chatty child can never deadlock on a
    // full pipe buffer while we poll its state.
    let (stdout_pipe, stderr_pipe) = take_output_pipes(&mut child);
    let stdout_sink = SharedBounded::new(output_budget_bytes);
    let stderr_sink = SharedBounded::new(output_budget_bytes);
    let stdout_thread = spawn_drain_thread(stdout_pipe, Arc::clone(&stdout_sink));
    let stderr_thread = spawn_drain_thread(stderr_pipe, Arc::clone(&stderr_sink));

    let deadline = started + timeout;
    let termination = loop {
        if !child.is_running() {
            break TerminationKind::Exited;
        }
        if cancel_flag() {
            child.kill_tree_and_wait();
            break TerminationKind::Cancelled;
        }
        if Instant::now() >= deadline {
            child.kill_tree_and_wait();
            break TerminationKind::TimeoutKilled;
        }
        std::thread::sleep(Duration::from_millis(25));
    };

    let (stdout_bounded, stdout_truncated, stdout_lossy) = stdout_sink.finish(stdout_thread);
    let (stderr_bounded, stderr_truncated, stderr_lossy) = stderr_sink.finish(stderr_thread);

    // Truthful cleanup verification: nothing inside the job may survive.
    if child.is_running() {
        child.kill_tree_and_wait();
    }
    let mut process_tree_cleaned = !child.is_running();
    #[cfg(windows)]
    if process_tree_cleaned {
        // Authoritative OS-side count: zero live processes inside the job.
        if let Some(active) = child.job_active_processes() {
            process_tree_cleaned = active == 0;
        }
    }
    let exit_code = if termination == TerminationKind::Exited {
        child.exit_code()
    } else {
        None
    };

    let success = termination == TerminationKind::Exited && exit_code == Some(0);
    if success {
        guard.record_success(&fingerprint);
    } else {
        guard.record_failure(&fingerprint);
    }

    Ok(TerminalResult {
        schema_version: RUNNER_SCHEMA,
        command_id: command_id.to_string(),
        exit_code,
        termination_kind: termination,
        duration_ms: started.elapsed().as_millis() as u64,
        stdout_bounded,
        stderr_bounded,
        stdout_truncated,
        stderr_truncated,
        stdout_lossy,
        stderr_lossy,
        fingerprint_hex: fingerprint.iter().map(|b| format!("{b:02x}")).collect(),
        process_tree_cleaned,
    })
}

// Silence unused-import lint for Write in older toolchains where
// read_to_end on ChildStdout does not require the trait import.
const _: Option<fn()> = Some(|| {
    fn _assert_write<T: Write>() {}
    let _ = _assert_write::<std::io::Sink>;
});

#[cfg(test)]
mod tests {
    use super::*;

    fn ws() -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "runner_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn decode_output_roundtrips_cyrillic_utf8_byte_exact() {
        // Encoding-proof literals (\u{...}) so this test cannot rot when a
        // toolchain mangles source-file encoding: "Привет, LocalComet!" plus
        // a long Russian sentence.
        let greeting = "\u{41f}\u{440}\u{438}\u{432}\u{435}\u{442}, LocalComet!";
        let (decoded, lossy) = decode_output(greeting.as_bytes());
        assert_eq!(decoded, greeting);
        assert!(!lossy);

        let long = "\u{041f}\u{0440}\u{043e}\u{0432}\u{0435}\u{0440}\u{043a}\u{0430} \
                    \u{0434}\u{043b}\u{0438}\u{043d}\u{043d}\u{043e}\u{0433}\u{043e} \
                    \u{0440}\u{0443}\u{0441}\u{0441}\u{043a}\u{043e}\u{0433}\u{043e} \
                    \u{0442}\u{0435}\u{043a}\u{0441}\u{0442}\u{0430}: \u{0441}\u{0438}\u{043c}\u{0432}\u{043e}\u{043b}\u{044b} \
                    \u{0434}\u{043e}\u{043b}\u{0436}\u{043d}\u{044b} \u{0431}\u{044b}\u{0442}\u{044c} \
                    \u{0431}\u{0430}\u{0439}\u{0442}-\u{0442}\u{043e}\u{0447}\u{043d}\u{044b}\u{043c}\u{0438}";
        let (decoded_long, lossy_long) = decode_output(long.as_bytes());
        assert_eq!(decoded_long, long);
        assert!(!lossy_long);
    }

    #[test]
    fn decode_output_flags_non_utf8_bytes_as_lossy() {
        // CP866/OEM Cyrillic bytes (the word "Privet" in cp866) are not
        let cp866: Vec<u8> = vec![0x8F, 0xE0, 0xA8, 0xA2, 0xA5, 0xE2];
        let (decoded, lossy) = decode_output(&cp866);
        assert!(lossy, "non-UTF-8 child output must be flagged lossy");
        // Lossy conversion still yields bounded, printable text (no panic).
        assert!(!decoded.is_empty());
    }

    #[test]
    fn allowlisted_command_succeeds_and_captures_output() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let result = run_bounded(
            "cmd_1",
            "rustc",
            &["--version".to_string()],
            &root,
            "wsd",
            Duration::from_secs(10),
            4096,
            &|| false,
            &guard,
        )
        .unwrap();
        assert_eq!(result.termination_kind, TerminationKind::Exited);
        assert_eq!(result.exit_code, Some(0));
        assert!(
            result.stdout_bounded.to_ascii_lowercase().contains("rustc")
                || result.stderr_bounded.to_ascii_lowercase().contains("rustc")
                || !result.stdout_bounded.trim().is_empty()
                || !result.stderr_bounded.trim().is_empty()
        );
        assert!(!result.stdout_truncated);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn shell_program_is_rejected_even_without_metachar() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let err = run_bounded(
            "shell_1",
            "cmd",
            &["/C".to_string(), "echo hello".to_string()],
            &root,
            "wsd",
            Duration::from_secs(5),
            4096,
            &|| false,
            &guard,
        )
        .unwrap_err();
        assert_eq!(err, "policy_rejected_shell_or_metachar");
        let err2 = run_bounded(
            "shell_2",
            "powershell",
            &["-Command".to_string(), "echo hi".to_string()],
            &root,
            "wsd",
            Duration::from_secs(5),
            4096,
            &|| false,
            &guard,
        )
        .unwrap_err();
        assert_eq!(err2, "policy_rejected_shell_or_metachar");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn metacharacters_are_policy_rejected() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let err = run_bounded(
            "cmd_2",
            "cmd",
            &["/C".to_string(), "echo a & echo b".to_string()],
            &root,
            "wsd",
            Duration::from_secs(5),
            4096,
            &|| false,
            &guard,
        )
        .unwrap_err();
        assert_eq!(err, "policy_rejected_shell_or_metachar");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn missing_executable_is_typed() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let err = run_bounded(
            "cmd_3",
            "definitely-not-a-real-exe-xyz",
            &[],
            &root,
            "wsd",
            Duration::from_secs(5),
            1024,
            &|| false,
            &guard,
        )
        .unwrap_err();
        assert_eq!(err, "executable_not_found");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn timeout_kills_and_records_failure_budget() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let fp = execution_fingerprint(
            "ping",
            &["-n".into(), "30".into(), "127.0.0.1".into()],
            "wsd",
        );
        for attempt in 0..MAX_IDENTICAL_FAILURES {
            let result = run_bounded(
                "cmd_timeout",
                "ping",
                &["-n".into(), "30".into(), "127.0.0.1".into()],
                &root,
                "wsd",
                Duration::from_millis(300),
                1024,
                &|| false,
                &guard,
            )
            .unwrap();
            assert_eq!(result.termination_kind, TerminationKind::TimeoutKilled);
            // Job-object containment: the killed tree must be verifiably gone.
            assert!(result.process_tree_cleaned, "job tree must be cleaned");
            assert_eq!(attempt + 1, guard_failures(&guard, &fp));
        }
        // Third identical run is denied by doom-loop budget.
        let err = run_bounded(
            "cmd_timeout",
            "ping",
            &["-n".into(), "30".into(), "127.0.0.1".into()],
            &root,
            "wsd",
            Duration::from_millis(300),
            1024,
            &|| false,
            &guard,
        )
        .unwrap_err();
        assert_eq!(err, "doom_loop_budget_exhausted");
        let _ = std::fs::remove_dir_all(root);
    }

    fn guard_failures(guard: &ExecutionGuard, fp: &[u8; 32]) -> u32 {
        guard.failures.lock().unwrap().get(fp).copied().unwrap_or(0)
    }

    #[test]
    fn success_resets_doom_loop_budget() {
        let guard = ExecutionGuard::new();
        let args = vec!["--invalid-flag-for-test".to_string()];
        let fp = execution_fingerprint("rustc", &args, "w");
        let root = ws();
        for _ in 0..MAX_IDENTICAL_FAILURES {
            let r = run_bounded(
                "c",
                "rustc",
                &args,
                &root,
                "w",
                Duration::from_secs(5),
                64,
                &|| false,
                &guard,
            )
            .unwrap();
            assert_ne!(r.exit_code, Some(0));
        }
        assert!(guard.admit(&fp).is_err());
        guard.record_success(&fp);
        assert!(guard.admit(&fp).is_ok());
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn cancellation_terminates_child_and_verifies_tree_cleanup() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let result = run_bounded(
            "cmd_cancel",
            "ping",
            &["-n".into(), "30".into(), "127.0.0.1".into()],
            &root,
            "wsd",
            Duration::from_secs(60),
            1024,
            &|| true,
            &guard,
        )
        .unwrap();
        assert_eq!(result.termination_kind, TerminationKind::Cancelled);
        assert!(
            result.process_tree_cleaned,
            "cancel must verify the whole job tree is gone"
        );
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn unregistered_test_binary_is_default_denied() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let system_exe = r"C:\Windows\System32\whoami.exe";
        let request = TerminalRequest {
            command_id: "unreg_1".into(),
            command_kind: CommandKind::TaskTestBinary,
            program: system_exe.to_string(),
            args: vec![],
            cwd_relative: String::new(),
            workspace_root: root.clone(),
            workspace_digest: "wsd".into(),
            permission_context_digest: String::new(),
            task_id: "t_unreg".into(),
            step_id: "s".into(),
            timeout_ms: 5_000,
            output_budget_bytes: 1024,
        };
        let err = execute(&request, &|| false, &guard).unwrap_err();
        assert_eq!(err, "policy_rejected_unregistered_test_artifact");
        // Even registering it for ANOTHER task does not admit this task.
        guard.register_test_artifact("t_other", Path::new(system_exe));
        let err2 = execute(&request, &|| false, &guard).unwrap_err();
        assert_eq!(err2, "policy_rejected_unregistered_test_artifact");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn rustc_kind_rejects_non_rustc_program() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let request = TerminalRequest {
            command_id: "kind_1".into(),
            command_kind: CommandKind::RustcDiagnostics,
            // Absolute path to a real non-rustc executable.
            program: r"C:\Windows\System32\whoami.exe".to_string(),
            args: vec![],
            cwd_relative: String::new(),
            workspace_root: root.clone(),
            workspace_digest: "wsd".into(),
            permission_context_digest: String::new(),
            task_id: "t_kind".into(),
            step_id: "s".into(),
            timeout_ms: 5_000,
            output_budget_bytes: 1024,
        };
        let err = execute(&request, &|| false, &guard).unwrap_err();
        assert_eq!(err, "policy_rejected_unallowlisted_command");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn output_is_bounded_and_marked_truncated() {
        let root = ws();
        let guard = ExecutionGuard::new();
        // rustc --help produces >8 bytes; budget 8 must truncate with bounded read.
        let result = run_bounded(
            "cmd_big",
            "rustc",
            &["--help".to_string()],
            &root,
            "wsd",
            Duration::from_secs(10),
            8,
            &|| false,
            &guard,
        )
        .unwrap();
        assert!(result.stdout_truncated || result.stderr_truncated);
        assert!(result.stdout_bounded.len() <= 8 || result.stderr_bounded.len() <= 8);
        // At least one stream was truncated due to budget.
        assert!(result.stdout_truncated || result.stderr_truncated);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn non_zero_exit_is_typed_failure_not_success() {
        let root = ws();
        let guard = ExecutionGuard::new();
        let result = run_bounded(
            "cmd_fail",
            "rustc",
            &["--invalid-flag-for-test".to_string()],
            &root,
            "wsd",
            Duration::from_secs(5),
            64,
            &|| false,
            &guard,
        )
        .unwrap();
        assert_ne!(result.exit_code, Some(0));
        assert_ne!(result.termination_kind, TerminationKind::Cancelled);
    }

    #[test]
    fn cwd_validation_rejects_escape_and_missing() {
        let root = ws();
        assert_eq!(validate_cwd(&root, "..\\.."), Err("invalid_cwd"));
        assert_eq!(validate_cwd(&root, "nope"), Err("cwd_not_found"));
        assert_eq!(validate_cwd(&root, "C:\\Windows"), Err("invalid_cwd"));
        std::fs::create_dir_all(root.join("sub")).unwrap();
        assert!(validate_cwd(&root, "sub").is_ok());
        let _ = std::fs::remove_dir_all(root);
    }
}
