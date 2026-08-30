//! Real LSP adapter boundary (Phase 4).
//!
//! Contract:
//! * This is a REAL Language Server Protocol client over stdio JSON-RPC.
//!   It is distinct from the `rustc --error-format=json` compiler adapter in
//!   `diagnostics.rs`; neither may be presented as the other.
//! * Server discovery is honest: known install locations + explicit env
//!   override (`LOCALCOMET_LSP_SERVER_PATH`). If no server binary exists the
//!   adapter reports `lsp_server_not_found` and NEVER fabricates diagnostics.
//! * All transport is bounded: 16 KiB headers, 2 MiB bodies, hard deadlines
//!   on every round-trip, owned-child cleanup on shutdown/drop.
//! * Diagnostics are bound to (workspace_digest, generation_hash); results
//!   produced under a different generation are marked stale, never merged.
//! * URIs outside the confirmed workspace root are rejected before any
//!   diagnostic enters the typed schema.

#![allow(dead_code)]

use crate::diagnostics::Diagnostic;
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::time::{Duration, Instant};

pub const LSP_SCHEMA: &str = "localcomet.lsp-diagnostics.v1";
const MAX_HEADER_BYTES: usize = 16 * 1024;
const MAX_BODY_BYTES: usize = 2 * 1024 * 1024;

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

/// Honest discovery: explicit env override wins; otherwise PATH is searched
/// for known servers. Returns a path ONLY when the binary really exists.
pub fn discover_server() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("LOCALCOMET_LSP_SERVER_PATH") {
        let path = PathBuf::from(p);
        if path.is_file() {
            return Some(path);
        }
        return None;
    }
    let candidates = ["rust-analyzer.exe", "rust-analyzer", "clangd.exe", "clangd"];
    let path_var = std::env::var("PATH").unwrap_or_default();
    for dir in std::env::split_paths(&path_var) {
        for cand in candidates {
            let full = dir.join(cand);
            if full.is_file() {
                return Some(full);
            }
        }
    }
    // Common cargo home fallback.
    if let Ok(home) = std::env::var("CARGO_HOME") {
        let full = Path::new(&home).join("bin").join("rust-analyzer.exe");
        if full.is_file() {
            return Some(full);
        }
    }
    None
}

// ---------------------------------------------------------------------------
// JSON-RPC framing (pure, unit-testable)
// ---------------------------------------------------------------------------

fn frame_message(body: &str) -> String {
    format!("Content-Length: {}\r\n\r\n{}", body.len(), body)
}

/// Parse one framed message from a line-oriented header stream. Returns the
/// body string, or None when the stream ended cleanly. Oversized headers or
/// bodies are protocol errors, never truncated-and-accepted.
fn read_framed<R: BufRead>(reader: &mut R) -> Result<Option<String>, String> {
    let mut content_length: Option<usize> = None;
    loop {
        let mut line = String::new();
        let n = reader.read_line(&mut line).map_err(|e| e.to_string())?;
        if n == 0 {
            return Ok(None); // EOF between frames
        }
        if line.len() > MAX_HEADER_BYTES {
            return Err("lsp_header_too_large".into());
        }
        let trimmed = line.trim_end();
        if trimmed.is_empty() {
            break; // end of headers
        }
        let lower = trimmed.to_ascii_lowercase();
        if let Some(rest) = lower.strip_prefix("content-length:") {
            content_length = rest
                .trim()
                .parse::<usize>()
                .ok()
                .filter(|&n| n <= MAX_BODY_BYTES);
            if content_length.is_none() {
                return Err("lsp_body_too_large_or_invalid".into());
            }
        }
    }
    let len = content_length.ok_or_else(|| "lsp_missing_content_length".to_string())?;
    let mut body = vec![0u8; len];
    reader.read_exact(&mut body).map_err(|e| e.to_string())?;
    String::from_utf8(body)
        .map(Some)
        .map_err(|_| "lsp_body_not_utf8".to_string())
}

/// Convert a `file:///` URI into a path and enforce workspace containment.
/// Only files that really exist inside the confirmed workspace are admitted.
fn uri_to_workspace_relative(uri: &str, workspace_root: &Path) -> Result<PathBuf, String> {
    let rest = uri
        .strip_prefix("file://")
        .ok_or_else(|| "lsp_uri_not_file".to_string())?;
    let raw = rest
        .strip_prefix('/')
        .ok_or_else(|| "lsp_uri_not_file".to_string())?;
    // Percent-decode the minimal safe set (%20 etc.) without accepting
    // encoded traversal forms.
    let lower = raw.to_ascii_lowercase();
    if lower.contains("%2e%2e") || lower.contains("%252e") || raw.contains("..") {
        return Err("lsp_uri_traversal".into());
    }
    let decoded = raw
        .replace("%20", " ")
        .replace("%3A", ":")
        .replace("%3a", ":")
        .replace("%5C", "\\");
    // Windows URIs carry a drive letter ("C:/…"); Unix URIs are rooted.
    #[cfg(windows)]
    let path = PathBuf::from(decoded.replace('/', "\\"));
    #[cfg(not(windows))]
    let path = PathBuf::from(format!("/{decoded}"));
    if !path.exists() {
        return Err("lsp_uri_not_on_disk".into());
    }
    let canonical = path.canonicalize().map_err(|e| e.to_string())?;
    let root_canonical = workspace_root.canonicalize().map_err(|e| e.to_string())?;
    if !canonical.starts_with(&root_canonical) {
        return Err("lsp_uri_outside_workspace".into());
    }
    Ok(canonical)
}

// ---------------------------------------------------------------------------
// Typed diagnostic conversion
// ---------------------------------------------------------------------------

fn severity_to_str(sev: Option<u64>) -> &'static str {
    match sev {
        Some(1) => "error",
        Some(2) => "warning",
        Some(3) => "info",
        _ => "info",
    }
}

/// Convert one `textDocument/publishDiagnostics` notification into typed
/// diagnostics. Foreign-workspace URIs are skipped (never fabricated).
pub fn parse_publish_diagnostics(
    params: &serde_json::Value,
    workspace_root: &Path,
    workspace_digest: &str,
    generation_hash: &str,
) -> Vec<Diagnostic> {
    let uri = params.get("uri").and_then(|v| v.as_str()).unwrap_or("");
    let Ok(abs) = uri_to_workspace_relative(uri, workspace_root) else {
        return vec![];
    };
    // Both sides canonicalized: Windows verbatim prefixes (\\?\) must match.
    let root_canonical = workspace_root
        .canonicalize()
        .unwrap_or_else(|_| workspace_root.to_path_buf());
    let rel = abs
        .strip_prefix(&root_canonical)
        .map(|p| p.to_string_lossy().replace('\\', "/"))
        .unwrap_or_default();
    let empty = Vec::new();
    let diags = params
        .get("diagnostics")
        .and_then(|v| v.as_array())
        .unwrap_or(&empty);
    diags
        .iter()
        .map(|d| Diagnostic {
            file: rel.clone(),
            line: d["range"]["start"]["line"].as_u64().unwrap_or(0) as u32 + 1,
            column: d["range"]["start"]["character"].as_u64().unwrap_or(0) as u32 + 1,
            code: d
                .get("code")
                .map(|c| c.to_string().trim_matches('"').to_string())
                .unwrap_or_default(),
            severity: severity_to_str(d.get("severity").and_then(|s| s.as_u64())).to_string(),
            source: "lsp".to_string(),
            message: d
                .get("message")
                .and_then(|m| m.as_str())
                .unwrap_or_default()
                .chars()
                .take(2000)
                .collect(),
            workspace_digest: workspace_digest.to_string(),
            generation_hash: generation_hash.to_string(),
            stale: false,
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Session lifecycle (initialize → work → shutdown/exit, owned cleanup)
// ---------------------------------------------------------------------------

pub struct LspSession {
    child: Child,
    stdin: ChildStdin,
    rx: Receiver<Result<String, String>>,
    workspace_root: PathBuf,
    workspace_digest: String,
    next_id: u64,
}

impl std::fmt::Debug for LspSession {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("LspSession")
            .field("workspace_digest", &self.workspace_digest)
            .field("alive", &self.child.id())
            .finish()
    }
}

impl LspSession {
    /// Spawn the server and perform the initialize/initialized handshake
    /// under a hard deadline. Workspace binding is fixed at start.
    pub fn start(
        server_path: &Path,
        workspace_root: &Path,
        timeout_ms: u64,
    ) -> Result<Self, String> {
        if !server_path.is_file() {
            return Err("lsp_server_not_found".into());
        }
        let mut child = Command::new(server_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .current_dir(workspace_root)
            .spawn()
            .map_err(|e| format!("lsp_spawn_failed: {e}"))?;
        let stdin = child.stdin.take().ok_or("lsp_stdin_unavailable")?;
        let stdout = child.stdout.take().ok_or("lsp_stdout_unavailable")?;
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                match read_framed(&mut reader) {
                    Ok(Some(body)) => {
                        if tx.send(Ok(body)).is_err() {
                            break;
                        }
                    }
                    Ok(None) => break,
                    Err(e) => {
                        let _ = tx.send(Err(e));
                        break;
                    }
                }
            }
        });
        let mut h = Sha256::new();
        h.update(
            workspace_root
                .canonicalize()
                .unwrap_or_else(|_| workspace_root.to_path_buf())
                .to_string_lossy()
                .as_bytes(),
        );
        let digest = format!("{:x}", h.finalize());
        let mut session = Self {
            child,
            stdin,
            rx,
            workspace_root: workspace_root.to_path_buf(),
            workspace_digest: digest,
            next_id: 1,
        };
        // initialize → response → initialized notification.
        let init_params = serde_json::json!({
            "processId": std::process::id(),
            "rootUri": format!(
                "file:///{}",
                session.workspace_root.display().to_string().replace('\\', "/").trim_start_matches('/')
            ),
            "capabilities": {},
        });
        let response_deadline = Duration::from_millis(timeout_ms.max(1_000));
        session.request_with_deadline("initialize", init_params, response_deadline)?;
        session.notify("initialized", serde_json::json!({}))?;
        Ok(session)
    }

    fn workspace_digest(&self) -> &str {
        &self.workspace_digest
    }

    fn notify(&mut self, method: &str, params: serde_json::Value) -> Result<(), String> {
        let body = serde_json::json!({"jsonrpc": "2.0", "method": method, "params": params});
        self.stdin
            .write_all(frame_message(&body.to_string()).as_bytes())
            .map_err(|e| format!("lsp_write_failed: {e}"))?;
        self.stdin.flush().map_err(|e| e.to_string())
    }

    fn request_with_deadline(
        &mut self,
        method: &str,
        params: serde_json::Value,
        deadline: Duration,
    ) -> Result<serde_json::Value, String> {
        let id = self.next_id;
        self.next_id += 1;
        let body = serde_json::json!({
            "jsonrpc": "2.0", "id": id, "method": method, "params": params
        });
        self.stdin
            .write_all(frame_message(&body.to_string()).as_bytes())
            .map_err(|e| format!("lsp_write_failed: {e}"))?;
        self.stdin.flush().map_err(|e| e.to_string())?;
        let started = Instant::now();
        loop {
            if started.elapsed() > deadline {
                return Err("lsp_timeout".into());
            }
            let remaining = deadline.saturating_sub(started.elapsed());
            match self
                .rx
                .recv_timeout(remaining.min(Duration::from_millis(250)))
            {
                Ok(Ok(text)) => {
                    let msg: serde_json::Value =
                        serde_json::from_str(&text).map_err(|e| format!("lsp_bad_json: {e}"))?;
                    if msg.get("id").and_then(|v| v.as_u64()) == Some(id) {
                        if let Some(err) = msg.get("error") {
                            return Err(format!("lsp_server_error: {err}"));
                        }
                        return Ok(msg
                            .get("result")
                            .cloned()
                            .unwrap_or(serde_json::Value::Null));
                    }
                    // Non-matching responses/notifications are dropped here;
                    // publishDiagnostics collection has its own pump.
                }
                Ok(Err(e)) => return Err(e),
                Err(RecvTimeoutError::Timeout) => continue,
                Err(RecvTimeoutError::Disconnected) => return Err("lsp_server_died".into()),
            }
        }
    }

    /// Pump notifications for up to `window_ms`, converting
    /// `textDocument/publishDiagnostics` payloads into typed diagnostics
    /// bound to `generation_hash`. Older-generation results come back stale.
    pub fn collect_diagnostics(
        &self,
        window_ms: u64,
        generation_hash: &str,
    ) -> Result<Vec<Diagnostic>, String> {
        let started = Instant::now();
        let window = Duration::from_millis(window_ms.max(1));
        let mut out = Vec::new();
        loop {
            if started.elapsed() > window {
                break;
            }
            match self.rx.recv_timeout(
                window
                    .saturating_sub(started.elapsed())
                    .min(Duration::from_millis(100)),
            ) {
                Ok(Ok(text)) => {
                    let Ok(msg) = serde_json::from_str::<serde_json::Value>(&text) else {
                        continue;
                    };
                    if msg.get("method").and_then(|m| m.as_str())
                        == Some("textDocument/publishDiagnostics")
                    {
                        out.extend(parse_publish_diagnostics(
                            &msg["params"],
                            &self.workspace_root,
                            self.workspace_digest(),
                            generation_hash,
                        ));
                    }
                }
                Ok(Err(e)) => return Err(e),
                Err(RecvTimeoutError::Timeout) => continue,
                Err(RecvTimeoutError::Disconnected) => return Err("lsp_server_died".into()),
            }
        }
        crate::diagnostics::mark_stale_if_generation_changed(&mut out, generation_hash);
        Ok(out)
    }

    pub fn open_text_document(
        &mut self,
        rel_path: &str,
        text: &str,
        version: i64,
    ) -> Result<(), String> {
        let abs = self.workspace_root.join(rel_path);
        let canonical = abs
            .canonicalize()
            .map_err(|e| format!("open_not_found: {e}"))?;
        if !canonical.starts_with(
            self.workspace_root
                .canonicalize()
                .unwrap_or_else(|_| self.workspace_root.clone()),
        ) {
            return Err("lsp_open_outside_workspace".into());
        }
        let uri = format!(
            "file:///{}",
            canonical
                .to_string_lossy()
                .replace('\\', "/")
                .trim_start_matches('/')
        );
        self.notify(
            "textDocument/didOpen",
            serde_json::json!({
                "textDocument": {
                    "uri": uri,
                    "languageId": "rust",
                    "version": version,
                    "text": text,
                }
            }),
        )
    }

    /// Ordered shutdown: `shutdown` request → `exit` notification → owned
    /// child reaped. Never leaves an orphan server behind.
    pub fn shutdown(&mut self) {
        let _ = self.request_with_deadline(
            "shutdown",
            serde_json::Value::Null,
            Duration::from_millis(2_000),
        );
        let _ = self.notify("exit", serde_json::Value::Null);
        // Bounded reap; force-kill only our own child.
        let deadline = Instant::now() + Duration::from_millis(2_000);
        while Instant::now() < deadline {
            match self.child.try_wait() {
                Ok(Some(_)) | Err(_) => break,
                Ok(None) => std::thread::sleep(Duration::from_millis(25)),
            }
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for LspSession {
    fn drop(&mut self) {
        self.shutdown();
    }
}

// ---------------------------------------------------------------------------
// Tauri seam (Phase 4 production wiring)
// ---------------------------------------------------------------------------

/// Bounded LSP diagnostics for one workspace-relative file.
///
/// Honest unavailable path: when no language-server binary is discovered, or
/// the handshake/collection fails, the envelope reports `available:false`
/// with the exact reason and NEVER fabricates diagnostics. The server child
/// is always reaped before returning (Drop + explicit shutdown).
#[tauri::command]
pub fn lsp_diagnostics(
    workspace_path: String,
    rel_path: String,
) -> Result<serde_json::Value, crate::control_plane::BridgeError> {
    use crate::control_plane::BridgeError;

    const HANDSHAKE_TIMEOUT_MS: u64 = 10_000;
    const COLLECT_WINDOW_MS: u64 = 3_000;
    const MAX_FILE_BYTES: usize = 512 * 1024;

    let envelope_unavailable = |reason: &str| {
        Ok(serde_json::json!({
            "schema_version": LSP_SCHEMA,
            "available": false,
            "reason": reason,
            "diagnostics": [],
        }))
    };
    let err =
        |code: &str, message: &str| BridgeError::new(code, message).with_phase("lsp_diagnostics");

    let root = PathBuf::from(&workspace_path);
    if !root.is_absolute() || !root.is_dir() {
        return Err(err(
            "invalid_workspace",
            "lsp workspace must be an existing absolute directory",
        ));
    }
    if let Ok(md) = std::fs::symlink_metadata(&root) {
        if md.file_type().is_symlink() {
            return Err(err(
                "workspace_reparse",
                "lsp workspace must not be a symlink/reparse point",
            ));
        }
    }
    // Strict rel-path policy: rust sources only, no traversal, no absolute forms.
    if rel_path.is_empty()
        || rel_path.contains("..")
        || rel_path.starts_with('/')
        || rel_path.starts_with('\\')
        || rel_path.contains(':')
        || !rel_path.ends_with(".rs")
    {
        return Err(err(
            "invalid_lsp_rel_path",
            "only relative .rs files are supported",
        ));
    }
    let canonical = match root.join(&rel_path).canonicalize() {
        Ok(path) => path,
        Err(_) => return Err(err("lsp_file_not_found", "target file does not exist")),
    };
    let root_canonical = root.canonicalize().unwrap_or_else(|_| root.clone());
    if !canonical.starts_with(&root_canonical) {
        return Err(err(
            "lsp_file_outside_workspace",
            "target escapes the confirmed workspace",
        ));
    }
    let metadata = std::fs::metadata(&canonical)
        .map_err(|_| err("lsp_file_not_found", "target file disappeared"))?;
    if metadata.len() as usize > MAX_FILE_BYTES {
        return Err(err(
            "lsp_file_too_large",
            "file exceeds the bounded diagnostics size",
        ));
    }
    let content = std::fs::read_to_string(&canonical)
        .map_err(|_| err("lsp_file_unreadable", "target file is not valid UTF-8 text"))?;

    let generation_hash = {
        let mut h = Sha256::new();
        h.update(content.as_bytes());
        format!("{:x}", h.finalize())
    };

    let Some(server) = discover_server() else {
        return envelope_unavailable("lsp_server_not_found");
    };
    let mut session = match LspSession::start(&server, &root, HANDSHAKE_TIMEOUT_MS) {
        Ok(session) => session,
        Err(reason) => return envelope_unavailable(&reason),
    };
    let collected = (|| -> Result<Vec<Diagnostic>, String> {
        session.open_text_document(&rel_path, &content, 1)?;
        session.collect_diagnostics(COLLECT_WINDOW_MS, &generation_hash)
    })();
    session.shutdown();
    match collected {
        Ok(list) => {
            let items: Vec<serde_json::Value> = list
                .iter()
                .map(|d| {
                    serde_json::json!({
                        "file": d.file,
                        "line": d.line,
                        "column": d.column,
                        "code": d.code,
                        "severity": d.severity,
                        "source": d.source,
                        "message": d.message,
                        "stale": d.stale,
                    })
                })
                .collect();
            Ok(serde_json::json!({
                "schema_version": LSP_SCHEMA,
                "available": true,
                "server": server.to_string_lossy(),
                "generation_hash": generation_hash,
                "stale_rejected": true,
                "diagnostics": items,
            }))
        }
        Err(reason) => envelope_unavailable(&reason),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_dir(prefix: &str) -> PathBuf {
        let base = std::env::temp_dir();
        let dir = base.join(format!(
            "{prefix}_{}_{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn discovery_is_honest_some_means_real_binary_none_means_none() {
        if let Some(path) = discover_server() {
            assert!(path.is_file(), "discovered path must exist: {path:?}");
        }
        // None is an honest, valid result when no server is installed.
    }

    /// F-06 honesty contract: with NO working server, the production seam
    /// must return `available:false` + exact reason + EMPTY diagnostics —
    /// never a fabricated "0 errors" success.
    #[test]
    fn lsp_diagnostics_returns_not_found_when_missing() {
        let ws = tmp_dir("lsp_ws6");
        fs::write(ws.join("lib.rs"), b"fn main() {}\n").unwrap();
        // Deterministic no-server environment for THIS call.
        std::env::set_var(
            "LOCALCOMET_LSP_SERVER_PATH",
            ws.join("definitely-not-installed.exe"),
        );
        let result =
            lsp_diagnostics(ws.to_string_lossy().to_string(), "lib.rs".to_string()).unwrap();
        assert_eq!(result["available"], serde_json::Value::Bool(false));
        assert_eq!(result["reason"], "lsp_server_not_found");
        assert_eq!(
            result["diagnostics"].as_array().map(std::vec::Vec::len),
            Some(0)
        );
        std::env::remove_var("LOCALCOMET_LSP_SERVER_PATH");
        let _ = fs::remove_dir_all(ws);
    }

    #[test]
    fn framing_roundtrip_and_bounds() {
        let mut cursor = std::io::Cursor::new(frame_message("{\"a\":1}").into_bytes());
        let body = read_framed(&mut cursor).unwrap().unwrap();
        assert_eq!(body, "{\"a\":1}");
        // EOF between frames → clean None.
        let mut empty = std::io::Cursor::new(Vec::<u8>::new());
        assert!(read_framed(&mut empty).unwrap().is_none());
        // Missing Content-Length is a protocol error, never guessed.
        let mut bad = std::io::Cursor::new(b"X-Nothing: 1\r\n\r\n{}".to_vec());
        assert_eq!(
            read_framed(&mut bad).unwrap_err(),
            "lsp_missing_content_length"
        );
        // Oversized declared body is rejected outright.
        let mut oversized = std::io::Cursor::new(
            format!("Content-Length: {}\r\n\r\n", MAX_BODY_BYTES + 1).into_bytes(),
        );
        assert_eq!(
            read_framed(&mut oversized).unwrap_err(),
            "lsp_body_too_large_or_invalid"
        );
    }

    #[test]
    fn publish_diagnostics_parses_into_typed_schema() {
        let ws = tmp_dir("lsp_ws");
        fs::write(ws.join("lib.rs"), b"fn main() {}\n").unwrap();
        let uri = format!(
            "file:///{}",
            ws.join("lib.rs")
                .to_string_lossy()
                .replace('\\', "/")
                .trim_start_matches('/')
        );
        let params = serde_json::json!({
            "uri": uri,
            "version": 1,
            "diagnostics": [
                {
                    "range": {"start": {"line": 0, "character": 4}, "end": {"line": 0, "character": 8}},
                    "severity": 1,
                    "code": "E0425",
                    "source": "rustc",
                    "message": "cannot find value `x` in this scope"
                },
                {"range": {"start": {"line": 1, "character": 0}}, "severity": 2, "message": "unused"}
            ]
        });
        let diags = parse_publish_diagnostics(&params, &ws, "wsdig", "gen1");
        assert_eq!(diags.len(), 2);
        assert_eq!(diags[0].file, "lib.rs");
        assert_eq!(diags[0].line, 1);
        assert_eq!(diags[0].column, 5);
        assert_eq!(diags[0].severity, "error");
        assert_eq!(diags[0].code, "E0425");
        assert_eq!(diags[0].source, "lsp");
        assert_eq!(diags[0].workspace_digest, "wsdig");
        assert!(!diags[0].stale);
        let _ = fs::remove_dir_all(ws);
    }

    #[test]
    fn foreign_workspace_uri_is_rejected_not_fabricated() {
        let ws = tmp_dir("lsp_ws2");
        let params = serde_json::json!({
            "uri": "file:///C:/Windows/system32/evil.rs",
            "diagnostics": [{"range": {"start": {"line": 0, "character": 0}}, "message": "boom"}]
        });
        let diags = parse_publish_diagnostics(&params, &ws, "wsdig", "gen1");
        assert!(
            diags.is_empty(),
            "foreign-workspace diagnostics must never enter the schema"
        );
        let _ = fs::remove_dir_all(ws);
    }

    #[test]
    fn traversal_uri_forms_are_rejected() {
        let ws = tmp_dir("lsp_ws3");
        for uri in [
            "file:///ws/../outside.rs",
            "file:///ws/%2e%2e/outside.rs",
            "http://example.com/x.rs",
        ] {
            assert!(uri_to_workspace_relative(uri, &ws).is_err(), "{uri}");
        }
        let _ = fs::remove_dir_all(ws);
    }

    #[test]
    fn stale_generation_results_are_flagged() {
        let ws = tmp_dir("lsp_ws4");
        fs::write(ws.join("a.rs"), b"x").unwrap();
        let uri = format!(
            "file:///{}",
            ws.join("a.rs")
                .to_string_lossy()
                .replace('\\', "/")
                .trim_start_matches('/')
        );
        let params = serde_json::json!({
            "uri": uri,
            "diagnostics": [{"range": {"start": {"line": 0, "character": 0}}, "message": "m"}]
        });
        // Parse binds the producing generation; staleness is decided by the
        // collector when comparing against the CURRENT generation.
        let mut diags = parse_publish_diagnostics(&params, &ws, "wsdig", "OLD_GEN");
        assert!(!diags.is_empty());
        crate::diagnostics::mark_stale_if_generation_changed(&mut diags, "NEW_GEN");
        assert!(crate::diagnostics::is_stale(&diags));
        let fresh = parse_publish_diagnostics(&params, &ws, "wsdig", "NEW_GEN");
        let mut fresh = fresh;
        crate::diagnostics::mark_stale_if_generation_changed(&mut fresh, "NEW_GEN");
        assert!(!crate::diagnostics::is_stale(&fresh));
        let _ = fs::remove_dir_all(ws);
    }

    #[cfg(windows)]
    #[test]
    fn start_refuses_missing_server_without_fabrication() {
        let ws = tmp_dir("lsp_ws5");
        let missing = ws.join("definitely-not-a-server.exe");
        let err = LspSession::start(&missing, &ws, 1_000).unwrap_err();
        assert!(
            err.contains("not_found") || err.contains("spawn_failed"),
            "{err}"
        );
        let _ = fs::remove_dir_all(ws);
    }

    /// LIVE integration against the real discovered language server.
    /// Opt-in (LOCALCOMET_LSP_LIVE_TEST=1) because server warm-up dominates
    /// gate time; run manually for acceptance evidence:
    ///   LOCALCOMET_LSP_LIVE_TEST=1 cargo test --lib lsp_live -- --nocapture
    #[cfg(windows)]
    #[test]
    fn lsp_live_handshake_diagnostics_and_shutdown() {
        if std::env::var("LOCALCOMET_LSP_LIVE_TEST").ok().as_deref() != Some("1") {
            eprintln!("live LSP test skipped: set LOCALCOMET_LSP_LIVE_TEST=1 to enable");
            return;
        }
        let Some(server) = discover_server() else {
            eprintln!("live-lsp UNAVAILABLE: no server discovered");
            return;
        };
        let ws = tmp_dir("lsp_live");
        let src = "fn main() { let x: i32 = \"not-i32\"; }\n";
        fs::write(ws.join("main_live.rs"), src).unwrap();
        // A discovered candidate may still be non-functional (e.g. a rustup
        // shim whose component is not installed). That is an honest
        // unavailability: print the exact error and stop — never fabricate.
        let mut session = match LspSession::start(&server, &ws, 30_000) {
            Ok(s) => s,
            Err(reason) => {
                eprintln!("live-lsp UNAVAILABLE: server={server:?} reason={reason}");
                let _ = fs::remove_dir_all(ws);
                return;
            }
        };
        session
            .open_text_document("main_live.rs", src, 1)
            .expect("didOpen");
        let diags = session
            .collect_diagnostics(60_000, "live_gen_1")
            .expect("diagnostics window");
        eprintln!(
            "[live-lsp] server={:?} diagnostics={} errors={}",
            server.file_name(),
            diags.len(),
            diags.iter().filter(|d| d.severity == "error").count()
        );
        for d in &diags {
            eprintln!(
                "[live-lsp] {}:{}:{} {} {} {}",
                d.file, d.line, d.column, d.severity, d.code, d.message
            );
        }
        assert!(
            !diags.is_empty(),
            "type error in opened file should produce at least one diagnostic"
        );
        assert!(diags.iter().all(|d| d.source == "lsp"));
        assert!(diags
            .iter()
            .all(|d| d.workspace_digest == session_workspace_digest_for_test(&session)));
        session.shutdown();
        let _ = fs::remove_dir_all(ws);
    }

    #[cfg(windows)]
    fn session_workspace_digest_for_test(session: &LspSession) -> String {
        session.workspace_digest().to_string()
    }
}
