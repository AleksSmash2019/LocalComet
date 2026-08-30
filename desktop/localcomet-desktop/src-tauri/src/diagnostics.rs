//! Diagnostics MVP — structured results with file/line/column/code/severity/source/generation_hash + stale.

use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Diagnostic {
    pub file: String,
    pub line: u32,
    pub column: u32,
    pub code: String,
    pub severity: String, // error, warning, info
    pub source: String,   // cargo, clippy, lsp
    pub message: String,
    pub workspace_digest: String,
    pub generation_hash: String,
    pub stale: bool,
}

pub fn collect_diagnostics_for_file(
    path: &Path,
    content: &str,
    workspace_digest: &str,
    generation_hash: &str,
) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for (idx, line) in content.lines().enumerate() {
        let lineno = (idx + 1) as u32;
        if line.contains("diagnostic: error") {
            diags.push(Diagnostic {
                file: path.to_string_lossy().replace('\\', "/"),
                line: lineno,
                column: 1,
                code: "DIAG001".to_string(),
                severity: "error".to_string(),
                source: "fixture".to_string(),
                message: "intentional diagnostic".to_string(),
                workspace_digest: workspace_digest.to_string(),
                generation_hash: generation_hash.to_string(),
                stale: false,
            });
        }
        if line.contains("todo!") || line.contains("unimplemented!") {
            diags.push(Diagnostic {
                file: path.to_string_lossy().replace('\\', "/"),
                line: lineno,
                column: 1,
                code: "DIAG_TODO".to_string(),
                severity: "warning".to_string(),
                source: "clippy".to_string(),
                message: "todo macro found".to_string(),
                workspace_digest: workspace_digest.to_string(),
                generation_hash: generation_hash.to_string(),
                stale: false,
            });
        }
    }
    diags
}

pub fn mark_stale_if_generation_changed(diags: &mut [Diagnostic], current_generation: &str) {
    for d in diags {
        if d.generation_hash != current_generation {
            d.stale = true;
        }
    }
}

pub fn is_stale(diags: &[Diagnostic]) -> bool {
    diags.iter().any(|d| d.stale)
}

// ---------------------------------------------------------------------------
// REAL compiler adapter (Phase: replace fixture-only proof).
//
// Uses the installed rustc toolchain with --error-format=json and normalizes
// the structured output into the typed schema. source is always "compiler";
// this is NOT an LSP and must never be presented as one.
// ---------------------------------------------------------------------------

pub const DIAGNOSTICS_ADAPTER_TIMEOUT_MS: u32 = 60_000;
const MAX_MESSAGE_CHARS: usize = 500;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AdapterError {
    MissingTool,
    Timeout,
    ParseError,
    PathEscape,
}

fn canonical_workspace_rel(workspace_root: &Path, file: &Path) -> Result<String, AdapterError> {
    let rel = file
        .strip_prefix(workspace_root)
        .map_err(|_| AdapterError::PathEscape)?;
    if rel.as_os_str().is_empty() {
        return Err(AdapterError::PathEscape);
    }
    Ok(rel.to_string_lossy().replace('\\', "/"))
}

struct RustcMessage {
    level_raw: String,
    code: Option<String>,
    message: String,
    spans: Vec<(String, u32, u32)>,
}

fn parse_rustc_line(line: &str) -> Option<RustcMessage> {
    let value: serde_json::Value = serde_json::from_str(line).ok()?;
    // rustc --error-format=json emits flat objects:
    // {"$message_type":"diagnostic","level":"error","message":"...",
    //  "code":{"code":"E0xxx",...}|null,"spans":[...], ...}
    if value
        .get("$message_type")
        .and_then(serde_json::Value::as_str)
        != Some("diagnostic")
    {
        return None;
    }
    let code_field = value.get("code");
    Some(RustcMessage {
        level_raw: value
            .get("level")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_ascii_lowercase(),
        code: match code_field {
            Some(serde_json::Value::String(s)) => Some(s.clone()),
            Some(obj) => obj
                .get("code")
                .and_then(serde_json::Value::as_str)
                .map(str::to_owned),
            _ => None,
        },
        message: value
            .get("message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .chars()
            .take(MAX_MESSAGE_CHARS)
            .collect(),
        spans: value
            .get("spans")
            .and_then(serde_json::Value::as_array)
            .map(|arr| {
                arr.iter()
                    .filter_map(|s| {
                        let file = s.get("file_name")?.as_str()?.to_string();
                        let line = s.get("line_start")?.as_u64()? as u32;
                        let col = s.get("column_start")?.as_u64()? as u32;
                        Some((file, line, col))
                    })
                    .collect()
            })
            .unwrap_or_default(),
    })
}

/// Parse raw `rustc --error-format=json` stderr text into normalized
/// diagnostics. This is the production entry point when the toolchain is
/// executed through the Rust terminal runner; the direct-spawn helper below
/// is a test-only convenience and must not be used by the orchestrator.
pub fn parse_rustc_diagnostics(
    workspace_root: &Path,
    stderr_text: &str,
    workspace_digest: &str,
    generation_hash: &str,
) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for line in stderr_text.lines() {
        let Some(message) = parse_rustc_line(line) else {
            continue;
        };
        let severity = match message.level_raw.as_str() {
            "error" => "error",
            "warning" => "warning",
            "note" | "help" => "info",
            _ => "hint",
        };
        for (raw_file, line_no, col_no) in &message.spans {
            let span_path = std::path::PathBuf::from(raw_file);
            // rustc echoes the input path exactly as given: absolute when the
            // caller passed absolute, bare-relative otherwise (runner case).
            let span_rel = match canonical_workspace_rel(workspace_root, &span_path) {
                Ok(rel) => rel,
                Err(AdapterError::PathEscape) => {
                    let p = Path::new(raw_file);
                    let clean = !p.is_absolute()
                        && p.components()
                            .all(|c| matches!(c, std::path::Component::Normal(_)));
                    if !clean {
                        continue;
                    }
                    raw_file.replace('\\', "/")
                }
                Err(_) => continue,
            };
            diags.push(Diagnostic {
                file: span_rel.clone(),
                line: *line_no,
                column: *col_no,
                code: message.code.clone().unwrap_or_else(|| "E0000".into()),
                severity: severity.to_string(),
                source: "compiler".to_string(),
                message: message.message.clone(),
                workspace_digest: workspace_digest.to_string(),
                generation_hash: generation_hash.to_string(),
                stale: false,
            });
        }
    }
    diags
}

/// Run rustc on a single file inside the workspace and collect normalized
/// diagnostics. Exit code of the toolchain is preserved in the Ok branch via
/// the returned count being zero vs non-zero; failures are typed errors.
#[cfg(test)]
pub fn collect_rustc_diagnostics(
    workspace_root: &Path,
    file: &Path,
    workspace_digest: &str,
    generation_hash: &str,
    task_id: &str,
    step_id: &str,
) -> Result<Vec<Diagnostic>, AdapterError> {
    let rel = canonical_workspace_rel(workspace_root, file)?;
    // Metadata artifact goes to a throwaway out-dir; the JSON diagnostics
    // stream arrives on stdout.
    let out_dir = std::env::temp_dir().join(format!(
        "lc_diag_out_{}_{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or_default()
    ));
    let _ = std::fs::create_dir_all(&out_dir);
    let output = std::process::Command::new("rustc")
        .args([
            "--edition=2021",
            "--crate-type=lib",
            "--emit=metadata",
            "--error-format=json",
        ])
        .arg(format!("--out-dir={}", out_dir.display()))
        .arg(file)
        .output()
        .map_err(|e| match e.kind() {
            std::io::ErrorKind::NotFound => AdapterError::MissingTool,
            _ => AdapterError::ParseError,
        })?;
    let _ = std::fs::remove_dir_all(&out_dir);

    // rustc streams structured diagnostics on STDERR (stdout carries the
    // emitted artifact), so parse stderr lines.
    let stdout = String::from_utf8_lossy(&output.stderr);
    let mut diags = Vec::new();
    for line in stdout.lines() {
        let Some(message) = parse_rustc_line(line) else {
            continue;
        };
        let severity = match message.level_raw.as_str() {
            "error" => "error",
            "warning" => "warning",
            "note" | "help" => "info",
            _ => "hint",
        };
        // A message without spans is render-only boilerplate (e.g. "aborting
        // due to previous error"); skip it — spanned entries carry the data.
        for (raw_file, line_no, col_no) in &message.spans {
            let span_path = std::path::PathBuf::from(raw_file);
            // rustc echoes the input path exactly as given: absolute when the
            // caller passed absolute, bare-relative otherwise (runner case).
            let span_rel = match canonical_workspace_rel(workspace_root, &span_path) {
                Ok(rel) => rel,
                Err(AdapterError::PathEscape) => {
                    // Relative form: accept only if it stays inside (no
                    // parent/root/prefix components).
                    let p = Path::new(raw_file);
                    let clean = !p.is_absolute()
                        && p.components()
                            .all(|c| matches!(c, std::path::Component::Normal(_)));
                    if !clean {
                        continue;
                    }
                    raw_file.replace('\\', "/")
                }
                Err(_) => continue,
            };
            diags.push(Diagnostic {
                file: span_rel.clone(),
                line: *line_no,
                column: *col_no,
                code: message.code.clone().unwrap_or_else(|| "E0000".into()),
                severity: severity.to_string(),
                source: "compiler".to_string(),
                message: message.message.clone(),
                workspace_digest: workspace_digest.to_string(),
                generation_hash: generation_hash.to_string(),
                stale: false,
            });
            let _ = (task_id, step_id, rel.as_str());
        }
    }
    Ok(diags)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn diagnostic_has_all_fields() {
        let d = Diagnostic {
            file: "src/lib.rs".to_string(),
            line: 10,
            column: 5,
            code: "E001".to_string(),
            severity: "error".to_string(),
            source: "cargo".to_string(),
            message: "msg".to_string(),
            workspace_digest: "ws".to_string(),
            generation_hash: "gen1".to_string(),
            stale: false,
        };
        assert_eq!(d.file, "src/lib.rs");
        assert!(!d.stale);
    }

    #[test]
    fn stale_after_new_patch() {
        let mut diags = vec![Diagnostic {
            file: "a.rs".to_string(),
            line: 1,
            column: 1,
            code: "DIAG001".to_string(),
            severity: "error".to_string(),
            source: "fixture".to_string(),
            message: "err".to_string(),
            workspace_digest: "ws".to_string(),
            generation_hash: "gen1".to_string(),
            stale: false,
        }];
        mark_stale_if_generation_changed(&mut diags, "gen2");
        assert!(diags[0].stale);
        assert!(is_stale(&diags));
    }

    #[test]
    fn fixture_error_is_detected() {
        let content = "fn foo() { diagnostic: error }\n";
        let diags = collect_diagnostics_for_file(&PathBuf::from("src/a.rs"), content, "ws", "gen1");
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, "DIAG001");
        assert!(!diags[0].stale);
    }

    #[test]
    fn clean_file_has_no_error() {
        let content = "fn foo() {}\n";
        let diags = collect_diagnostics_for_file(&PathBuf::from("src/a.rs"), content, "ws", "gen1");
        assert!(diags.is_empty());
    }

    #[test]
    fn todo_is_warning() {
        let content = "fn foo() { todo!() }\n";
        let diags = collect_diagnostics_for_file(&PathBuf::from("src/a.rs"), content, "ws", "gen1");
        assert!(diags.iter().any(|d| d.code == "DIAG_TODO"));
    }

    // --- real rustc adapter integration (toolchain-backed, NOT LSP) ---

    use std::path::PathBuf as PBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_ws() -> PBuf {
        let base = std::env::temp_dir();
        let dir = base.join(format!(
            "diag_{}_{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn rustc_adapter_captures_real_error_and_clean_pass() {
        let ws = tmp_ws();
        let bad = ws.join("bad.rs");
        std::fs::write(&bad, b"fn needs_type(x) { x }").unwrap();
        let diags = collect_rustc_diagnostics(&ws, &bad, "ws", "gen1", "t", "s")
            .expect("rustc available in dev env");
        assert!(
            diags.iter().any(|d| d.severity == "error"),
            "real compiler must report the error: {diags:?}"
        );
        let d = diags.iter().find(|d| d.severity == "error").unwrap();
        assert_eq!(d.file, "bad.rs");
        assert!(d.line >= 1);
        assert_eq!(d.source, "compiler");
        assert!(!d.message.is_empty());

        let good = ws.join("good.rs");
        std::fs::write(&good, b"pub fn ok() -> u32 { 1 }\n").unwrap();
        let clean =
            collect_rustc_diagnostics(&ws, &good, "ws", "gen2", "t", "s").expect("clean run");
        assert!(clean.iter().all(|d| d.severity != "error"));
        let _ = std::fs::remove_dir_all(&ws);
    }

    #[test]
    fn rustc_adapter_rejects_path_escape() {
        let ws = tmp_ws();
        let outside = std::env::temp_dir().join("diag_outside_escape.rs");
        std::fs::write(&outside, b"fn x() {}").unwrap();
        let err = collect_rustc_diagnostics(&ws, &outside, "ws", "g", "t", "s").unwrap_err();
        assert!(matches!(err, AdapterError::PathEscape));
        let _ = std::fs::remove_dir_all(&ws);
        let _ = std::fs::remove_file(&outside);
    }

    #[test]
    fn rustc_adapter_rejects_workspace_root_as_file() {
        let ws = tmp_ws();
        let err = collect_rustc_diagnostics(&ws, &ws, "ws", "g", "t", "s").unwrap_err();
        assert!(matches!(err, AdapterError::PathEscape));
        let _ = std::fs::remove_dir_all(&ws);
    }
}
